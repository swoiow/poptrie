use memmap2::Mmap;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs::File;
use std::net::IpAddr;

#[pyclass]
struct IpSearcher {
    mmap: Mmap,
    nodes_start: usize,
    values_start: usize,
    values_count: usize,
}

#[pymethods]
impl IpSearcher {
    #[new]
    fn new(path: String) -> PyResult<Self> {
        let file = File::open(path)?;
        let mmap = unsafe { Mmap::map(&file)? };
        let mut nodes_start = 0;
        let mut values_start = mmap.len();
        let mut values_count = 0;

        if mmap.len() >= Self::HEADER_SIZE && &mmap[0..4] == Self::MAGIC {
            let node_count = u32::from_le_bytes(mmap[4..8].try_into().unwrap()) as usize;
            values_count = u32::from_le_bytes(mmap[8..12].try_into().unwrap()) as usize;
            let nodes_bytes = node_count.checked_mul(Self::NODE_SIZE).ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Invalid bin file: node count overflow.",
                )
            })?;
            let values_bytes = values_count.checked_mul(2).ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Invalid bin file: values count overflow.",
                )
            })?;
            let expected_len = Self::HEADER_SIZE + nodes_bytes + values_bytes;
            if mmap.len() != expected_len {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Invalid bin file: size mismatch.",
                ));
            }
            nodes_start = Self::HEADER_SIZE;
            values_start = Self::HEADER_SIZE + nodes_bytes;
        } else if mmap.len() % Self::NODE_SIZE != 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Invalid bin file: alignment mismatch (expected 72).",
            ));
        }

        Ok(IpSearcher {
            mmap,
            nodes_start,
            values_start,
            values_count,
        })
    }

    /// 核心查询逻辑：支持 IPv4 (4字节) 和 IPv6 (16字节)
    fn contains_ip(&self, ip_bytes: &[u8]) -> bool {
        let mut cursor = self.nodes_start;
        // 获取裸指针以绕过切片边界检查
        let base_ptr = self.mmap.as_ptr();

        for &byte in ip_bytes {
            unsafe {
                let node_ptr = base_ptr.add(cursor);

                // 节点布局:
                // 0-31: ChildBitmap
                // 32-63: LeafBitmap
                // 64-67: BaseOffset (u32)
                // 68-71: BaseIndex (u32, only if leaf)

                // 1. 检查 LeafBitmap (偏移 32)
                // 这里的位操作展开后比函数调用略快，且避免了重复计算 indices
                let byte_index = (byte as usize) >> 3;
                let bit_index = 7 - (byte & 7);
                let bit_mask = 1 << bit_index;

                let leaf_byte = *node_ptr.add(32 + byte_index);
                if (leaf_byte & bit_mask) != 0 {
                    return true;
                }

                // 2. 检查 ChildBitmap (偏移 0)
                let child_byte = *node_ptr.add(byte_index);
                if (child_byte & bit_mask) == 0 {
                    return false;
                }

                // 3. 计算跳转偏移
                let base_offset = (node_ptr.add(64) as *const u32).read_unaligned() as usize;

                // 计算 ChildBitmap 中当前位之前的 1 的个数 (Popcount)
                let count = self.popcount_unsafe(node_ptr, byte_index, bit_index as usize);

                cursor = base_offset + (count * Self::NODE_SIZE);
            }
        }
        false
    }

    /// 返回国家代码 (u16)，未命中返回 0
    fn lookup_code(&self, ip_bytes: &[u8]) -> u16 {
        let mut cursor = self.nodes_start;
        let base_ptr = self.mmap.as_ptr();

        for &byte in ip_bytes {
            unsafe {
                let node_ptr = base_ptr.add(cursor);

                let byte_index = (byte as usize) >> 3;
                let bit_index = 7 - (byte & 7);
                let bit_mask = 1 << bit_index;

                // 1. Check Leaf
                let leaf_byte = *node_ptr.add(32 + byte_index);
                if (leaf_byte & bit_mask) != 0 {
                    if self.values_count == 0 {
                        return 0;
                    }

                    let base_index = (node_ptr.add(68) as *const u32).read_unaligned() as usize;

                    // 计算 LeafBitmap popcount
                    let offset =
                        self.popcount_unsafe(node_ptr.add(32), byte_index, bit_index as usize);

                    let value_index = base_index + offset;
                    if value_index >= self.values_count {
                        return 0;
                    }

                    // 读取值: values_start + index * 2
                    let value_pos = self.values_start + (value_index * 2);
                    // 确保不越界 (虽然理论上逻辑保证了，但 values_start 计算依赖文件长度)
                    // 这里为了极致性能假设文件格式正确，使用 unsafe 读取
                    // 也可以用 get_unchecked
                    let val_ptr = base_ptr.add(value_pos) as *const u16;
                    return val_ptr.read_unaligned();
                }

                // 2. Check Child
                let child_byte = *node_ptr.add(byte_index);
                if (child_byte & bit_mask) == 0 {
                    return 0;
                }

                // 3. Jump
                let base_offset = (node_ptr.add(64) as *const u32).read_unaligned() as usize;
                let count = self.popcount_unsafe(node_ptr, byte_index, bit_index as usize);

                cursor = base_offset + (count * Self::NODE_SIZE);
            }
        }
        0
    }

    fn contains_packed(&self, packed_ips: &[u8], is_v6: bool) -> Vec<bool> {
        let ip_stride = if is_v6 { 16 } else { 4 };

        // 使用 Rayon 并行处理
        packed_ips
            .par_chunks(ip_stride)
            .map(|ip_chunk| self.contains_ip(ip_chunk))
            .collect()
    }

    fn contains_strings(&self, py: Python<'_>, ips: Vec<String>) -> Vec<bool> {
        py.detach(|| {
            ips.into_par_iter()
                .map(|ip_str| match ip_str.parse::<IpAddr>() {
                    Ok(IpAddr::V4(v4)) => self.contains_ip(&v4.octets()),
                    Ok(IpAddr::V6(v6)) => self.contains_ip(&v6.octets()),
                    Err(_) => false,
                })
                .collect()
        })
    }

    fn lookup_codes_packed(&self, packed_ips: &[u8], is_v6: bool) -> Vec<u16> {
        let ip_stride = if is_v6 { 16 } else { 4 };

        // 使用 Rayon 并行处理
        packed_ips
            .par_chunks(ip_stride)
            .map(|ip_chunk| self.lookup_code(ip_chunk))
            .collect()
    }

    fn lookup_codes_strings(&self, py: Python<'_>, ips: Vec<String>) -> Vec<u16> {
        py.detach(|| {
            ips.into_par_iter()
                .map(|ip_str| match ip_str.parse::<IpAddr>() {
                    Ok(IpAddr::V4(v4)) => self.lookup_code(&v4.octets()),
                    Ok(IpAddr::V6(v6)) => self.lookup_code(&v6.octets()),
                    Err(_) => 0,
                })
                .collect()
        })
    }
}

impl IpSearcher {
    const NODE_SIZE: usize = 72;
    const HEADER_SIZE: usize = 16;
    const MAGIC: &'static [u8; 4] = b"PTV2";

    /// 内部使用的 unsafe popcount，假设 bitmap_ptr 有效
    #[inline(always)]
    unsafe fn popcount_unsafe(
        &self,
        bitmap_ptr: *const u8,
        byte_index: usize,
        bit_index: usize,
    ) -> usize {
        let mut count: usize = 0;

        // 1. 以 u64 为单位统计，减少循环次数
        // bitmap 是 32 字节，也就是 4 个 u64
        let u64_ptr = bitmap_ptr as *const u64;
        let chunk_count = byte_index / 8;

        for i in 0..chunk_count {
            // read_unaligned handles alignment issues if any
            let val = u64_ptr.add(i).read_unaligned();
            count += val.count_ones() as usize;
        }

        // 2. 统计剩余完整字节
        for i in (chunk_count * 8)..byte_index {
            count += (*bitmap_ptr.add(i)).count_ones() as usize;
        }

        // 3. 统计当前字节内的位
        // 目标是统计当前字节中，位索引 *大于* bit_index 的那些位 (在 Big-Endian 视角下是左边，但在我们的 bit_index 算法下：)
        // bit_index = 7 - (byte % 8).
        // byte: 7 6 5 4 3 2 1 0 (bit index)
        // value: 1 0 0 0 0 0 0 0 (0x80) -> bit index 7
        // 我们要统计的是逻辑上“在这之前”的位。
        // Trie 的逻辑通常是从 MSB 到 LSB 遍历。
        // 如果我们走到 bit_index，说明之前的 bit (bit_index + 1 到 7) 都是 0 (或者在路径上)。
        // 但是 popcount 是统计当前层级，在该 child 之前有多少个其他 child。
        // 在 byte 内部，bit 7 (0x80) 对应第一个 child，bit 0 (0x01) 对应最后一个。
        // 所以如果要找 bit 5，我们需要统计 bit 7 和 bit 6 是否为 1。
        // 也就是统计值比 (1 << bit_index) 更大的位。

        // 掩码：保留比当前位更高的位 (即左边的位)
        // Ex: bit_index = 5 (00100000). We want 11000000.
        // mask = 0xFF << (5 + 1) = 0xFF << 6 = 11000000. Correct.
        let mask = if bit_index == 7 {
            0
        } else {
            0xFF << (bit_index + 1)
        };

        count += (*bitmap_ptr.add(byte_index) & mask).count_ones() as usize;

        count
    }
}

#[pymodule]
fn poptrie(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<IpSearcher>()?;
    Ok(())
}
