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
        let mut cursor: usize = self.nodes_start;

        for &byte in ip_bytes {
            // 节点布局: 0-31 ChildBitmap, 32-63 LeafBitmap, 64-67 BaseOffset
            let child_bitmap = &self.mmap[cursor..cursor + 32];
            let leaf_bitmap = &self.mmap[cursor + 32..cursor + 64];

            // 1. 检查当前步长是否匹配 (Leaf)
            if self.check_bit(leaf_bitmap, byte) {
                return true;
            }

            // 2. 检查是否有子节点
            if !self.check_bit(child_bitmap, byte) {
                return false;
            }

            // 3. 计算跳转偏移 (Popcount)
            // 读取 4 字节的 BaseOffset (小端序)
            let base_offset =
                u32::from_le_bytes(self.mmap[cursor + 64..cursor + 68].try_into().unwrap())
                    as usize;

            // 获取当前字节之前的 '1' 的数量，确定子节点索引
            let index = self.get_popcount(child_bitmap, byte);
            cursor = base_offset + (index * Self::NODE_SIZE);
        }
        false
    }

    /// 返回国家代码 (u16)，未命中返回 0
    fn lookup_code(&self, ip_bytes: &[u8]) -> u16 {
        let mut cursor: usize = self.nodes_start;

        for &byte in ip_bytes {
            let child_bitmap = &self.mmap[cursor..cursor + 32];
            let leaf_bitmap = &self.mmap[cursor + 32..cursor + 64];

            if self.check_bit(leaf_bitmap, byte) {
                if self.values_count == 0 {
                    return 0;
                }
                let base_index =
                    u32::from_le_bytes(self.mmap[cursor + 68..cursor + 72].try_into().unwrap())
                        as usize;
                let offset = self.get_popcount(leaf_bitmap, byte);
                let value_index = base_index + offset;
                if value_index >= self.values_count {
                    return 0;
                }
                let value_pos = self.values_start + (value_index * 2);
                return u16::from_le_bytes(self.mmap[value_pos..value_pos + 2].try_into().unwrap());
            }

            if !self.check_bit(child_bitmap, byte) {
                return 0;
            }

            let base_offset =
                u32::from_le_bytes(self.mmap[cursor + 64..cursor + 68].try_into().unwrap())
                    as usize;
            let index = self.get_popcount(child_bitmap, byte);
            cursor = base_offset + (index * Self::NODE_SIZE);
        }
        0
    }

    fn contains_packed(&self, packed_ips: &[u8], is_v6: bool) -> Vec<bool> {
        let ip_stride = if is_v6 { 16 } else { 4 };

        packed_ips
            .chunks_exact(ip_stride)
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

        packed_ips
            .chunks_exact(ip_stride)
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

    #[inline]
    fn check_bit(&self, bitmap: &[u8], byte: u8) -> bool {
        let byte_index = (byte >> 3) as usize;
        let bit_index = 7 - (byte % 8); // 对应 Python 的 (1 << (7 - (k % 8)))
        (bitmap[byte_index] >> bit_index) & 1 == 1
    }

    #[inline]
    fn get_popcount(&self, bitmap: &[u8], byte: u8) -> usize {
        let byte_index = (byte >> 3) as usize;
        let bit_index = 7 - (byte % 8);
        let mut count: usize = 0;

        // 1. 以 u64 为单位统计，减少循环次数
        let full_byte_count = byte_index;
        let chunk_count = full_byte_count / 8;
        for i in 0..chunk_count {
            let start = i * 8;
            let value = u64::from_le_bytes(bitmap[start..start + 8].try_into().unwrap());
            count += value.count_ones() as usize;
        }
        for i in (chunk_count * 8)..full_byte_count {
            count += bitmap[i].count_ones() as usize;
        }

        // 2. 累加当前字节中，目标位“左侧”所有 1 的个数
        // 我们需要一个掩码来保留比 bit_in_byte 更高的位
        // 例如：如果 bit_in_byte 是 5 (二进制 00100000)，
        // 我们需要掩码 11000000 来计算它之前的 1
        let mask = if bit_index == 7 {
            0
        } else {
            0xFF << (bit_index + 1)
        };

        count += (bitmap[byte_index] & mask).count_ones() as usize;

        // 返回值即为该子节点在子节点数组中的索引（从 0 开始）
        count
    }
}

#[pymodule]
fn poptrie(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<IpSearcher>()?;
    Ok(())
}
