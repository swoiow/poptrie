use memmap2::Mmap;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs::File;
use std::net::IpAddr;

#[pyclass]
struct IpSearcher {
    mmap: Mmap,
}

#[pymethods]
impl IpSearcher {
    #[new]
    fn new(path: String) -> PyResult<Self> {
        let file = File::open(path)?;
        let mmap = unsafe { Mmap::map(&file)? };
        if mmap.len() % Self::NODE_SIZE != 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Invalid bin file: alignment mismatch (expected 72).",
            ));
        }
        Ok(IpSearcher { mmap })
    }

    /// 核心查询逻辑：支持 IPv4 (4字节) 和 IPv6 (16字节)
    fn is_china_ip(&self, ip_bytes: &[u8]) -> bool {
        let mut cursor: usize = 0;

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

    /// 极致性能版：接收扁平化字节流（每 4 或 16 字节代表一个 IP）
    fn batch_check_packed(&self, packed_ips: &[u8], is_v6: bool) -> Vec<bool> {
        let ip_stride = if is_v6 { 16 } else { 4 };

        // 使用 chunks_exact 确保每次切出固定长度的 IP 字节块
        // 这是极致性能的关键：内存完全连续，没有 Python 对象开销
        packed_ips
            .chunks_exact(ip_stride)
            .map(|ip_chunk| self.is_china_ip(ip_chunk))
            .collect()
    }

    fn batch_check_strings(&self, py: Python<'_>, ips: Vec<String>) -> Vec<bool> {
        py.allow_threads(|| {
            ips.into_par_iter()
                .map(|ip_str| match ip_str.parse::<IpAddr>() {
                    Ok(IpAddr::V4(v4)) => self.is_china_ip(&v4.octets()),
                    Ok(IpAddr::V6(v6)) => self.is_china_ip(&v6.octets()),
                    Err(_) => false,
                })
                .collect()
        })
    }
}

impl IpSearcher {
    const NODE_SIZE: usize = 72;

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
            let value =
                u64::from_le_bytes(bitmap[start..start + 8].try_into().unwrap());
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
