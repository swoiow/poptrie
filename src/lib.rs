use memmap2::Mmap;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rayon::prelude::*;
use std::fs::File;

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
        Ok(IpSearcher { mmap })
    }

    /// 核心查询逻辑：支持 IPv4 (4字节) 和 IPv6 (16字节)
    fn is_china_ip(&self, ip_bytes: &[u8]) -> bool {
        let mut curr_ptr: usize = 0;
        let node_size: usize = 68;

        for &byte in ip_bytes {
            // 节点布局: 0-31 ChildBitmap, 32-63 LeafBitmap, 64-67 BaseOffset
            let child_bm = &self.mmap[curr_ptr..curr_ptr + 32];
            let leaf_bm = &self.mmap[curr_ptr + 32..curr_ptr + 64];

            // 1. 检查当前步长是否匹配 (Leaf)
            if self.check_bit(leaf_bm, byte) {
                return true;
            }

            // 2. 检查是否有子节点
            if !self.check_bit(child_bm, byte) {
                return false;
            }

            // 3. 计算跳转偏移 (Popcount)
            // 读取 4 字节的 BaseOffset (小端序)
            let base_offset =
                u32::from_le_bytes(self.mmap[curr_ptr + 64..curr_ptr + 68].try_into().unwrap())
                    as usize;

            // 获取当前字节之前的 '1' 的数量，确定子节点索引
            let index = self.get_popcount(child_bm, byte);
            curr_ptr = base_offset + (index * node_size);
        }
        false
    }

    // 这里的 Bound<'_, PyBytes> 允许我们直接访问 Python 的内存
    fn batch_check(&self, ip_list: Vec<Bound<'_, PyBytes>>) -> Vec<bool> {
        ip_list
            .into_iter()
            .map(|py_bytes| {
                // as_bytes() 返回 &[u8]，不需要拷贝数据
                self.is_china_ip(py_bytes.as_bytes())
            })
            .collect()
    }

    /// 极致性能版：接收一个扁平化的字节流（每 4 或 16 字节代表一个 IP）
    fn batch_check_packed(&self, packed_ips: &[u8], is_v6: bool) -> Vec<bool> {
        let stride = if is_v6 { 16 } else { 4 };

        // 使用 chunks_exact 确保每次切出固定长度的 IP 字节块
        // 这是极致性能的关键：内存完全连续，没有 Python 对象开销
        packed_ips
            .chunks_exact(stride)
            .map(|ip_chunk| self.is_china_ip(ip_chunk))
            .collect()
    }

    fn batch_check_packed_parallel(
        &self,
        py: Python<'_>,
        packed_ips: &[u8],
        is_v6: bool,
    ) -> Vec<bool> {
        let stride = if is_v6 { 16 } else { 4 };

        // par_chunks_exact 是 Rayon 提供的并行切片方法
        py.allow_threads(|| {
            packed_ips
                .par_chunks_exact(stride)
                .map(|ip_chunk| self.is_china_ip(ip_chunk))
                .collect()
        })
    }
}

impl IpSearcher {
    #[inline]
    fn check_bit(&self, bitmap: &[u8], byte: u8) -> bool {
        let idx = (byte >> 3) as usize;
        let bit = 7 - (byte % 8); // 对应 Python 的 (1 << (7 - (k % 8)))
        (bitmap[idx] >> bit) & 1 == 1
    }

    #[inline]
    fn get_popcount(&self, bitmap: &[u8], byte: u8) -> usize {
        let byte_idx = (byte >> 3) as usize;
        let bit_in_byte = 7 - (byte % 8);
        let mut count = 0;

        // 1. 累加之前所有字节中 1 的个数
        for i in 0..byte_idx {
            count += bitmap[i].count_ones() as usize;
        }

        // 2. 累加当前字节中，目标位“左侧”所有 1 的个数
        // 我们需要一个掩码来保留比 bit_in_byte 更高的位
        // 例如：如果 bit_in_byte 是 5 (二进制 00100000)，
        // 我们需要掩码 11000000 来计算它之前的 1
        let mask = if bit_in_byte == 7 {
            0
        } else {
            0xFF << (bit_in_byte + 1)
        };

        count += (bitmap[byte_idx] & mask).count_ones() as usize;

        // 返回值即为该子节点在子节点数组中的索引（从 0 开始）
        count
    }
}

#[pymodule]
fn poptrie(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<IpSearcher>()?;
    Ok(())
}
