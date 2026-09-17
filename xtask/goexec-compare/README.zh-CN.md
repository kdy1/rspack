# 原生编译器：Tokio 与 goexec

这是原生 Rust Compiler API 的实验性执行器切换。基准程序的 `goexec` feature
启用固定 Git 提交的优化版本，包括工作线程本地队列、批量任务窃取和分片任务注册表。
默认构建仍使用 Tokio；Rayon 及 Tokio 的 task-local、同步原语继续保留。

此实验未迁移 Node/NAPI、JavaScript 插件或 loader、watch 定时器、网络及持久缓存后台运行时。
请勿在 Node binding 中全局开启这个实验 feature。基准测试禁用了持久缓存。

在仓库根目录运行：

```sh
python3 xtask/goexec-compare/prepare-fixtures.py
cargo build --locked --profile executor-bench -p rspack_goexec_compare
cp target/executor-bench/rspack_goexec_compare target/goexec-compare/rspack-tokio
cargo build --locked --profile executor-bench -p rspack_goexec_compare --features goexec
cp target/executor-bench/rspack_goexec_compare target/goexec-compare/rspack-goexec
target/goexec-compare/rspack-goexec target/goexec-compare/fixtures threejs-10x development 16 2 3
```

使用仓库固定的 Rust 工具链、Python 3，以及用于 fixture 的 pnpm 10.11.0。
参数依次为 fixture 目录、项目、模式、线程数、预热次数和测量次数。
每次编译会验证输出文件；主要计时区间是包含输出写入的 `Compiler::run()`。

归档结果来自 2026-09-17 的 Apple M5 Max。16 线程 Three.js-10x 开发构建中，
旧 goexec 为 155.70 ms，优化版本为 98.24 ms，Tokio 为 104.91 ms。
这不是所有条件下的提升：单线程时优化版本仍比 Tokio 慢约 12%。
所有 1,365 次归档构建的输出哈希、模块数量和字节数量一致。

[英文说明](README.md)包含完整测试范围、相同 macOS QoS 的设置方式、统计方法、
原始数据及已知限制。归档数据是在发布本分支之前取得的，不是此次上传时重新测量的结果。
