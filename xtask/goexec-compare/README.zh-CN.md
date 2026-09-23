# 原生编译器：Tokio 与 goexec

这是原生 Rust Compiler API 的实验性执行器切换。基准程序的 `goexec` feature
启用固定 Git 提交的
[goexec 0.1.3 `f5d82e14d8b068ecd0894065d3457bcf4ce33c54`](https://github.com/dudykr/ddbase/commit/f5d82e14d8b068ecd0894065d3457bcf4ce33c54)
（[PR #104](https://github.com/dudykr/ddbase/pull/104)）。多个执行许可时使用本地 LIFO 队列，
定期优先处理最旧任务；单许可时使用 FIFO。保留批量任务窃取和分片任务注册表，
恢复较简单的任务取消及窃取目标管理，并合并入队唤醒通知。依赖及其传递版本已固定在
Cargo.lock 中，无需本地路径覆盖。此分支已合入 upstream Rspack main 的
`cbf189da225ee607d9f66197f0ad8e50d8258c57`。
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

## 最新 main 验证 — 2026-09-23

在同一台 Apple M3 Max 上重新构建，使用 upstream Rspack main
`cbf189da225ee607d9f66197f0ad8e50d8258c57` 和 goexec main
`f5d82e14d8b068ecd0894065d3457bcf4ce33c54`（0.1.3）。合并没有冲突，
也无需修改执行器集成的 Rust 实现。goexec 的 Rust 源码与之前测量的调度器一致，
main 更新仅涉及版本号和 README。

Three.js-10x，执行器和 Rayon 均为 **12 线程**，七组配对进程，
每个版本、每种条件保留 21 次测量：

| 模式 | Tokio 中位数 | goexec 0.1.3 中位数 | 相对 Tokio 的配对耗时变化 [95% CI] |
|---|---:|---:|---:|
| 开发构建 | 143.06 ms | 116.89 ms | -18.82% [-20.74, -17.11] |
| Source map | 277.11 ms | 246.61 ms | -11.62% [-12.57, -10.63] |
| 压缩 | 1218.97 ms | 1187.06 ms | -2.89% [-3.85, -1.88] |

16 线程下，开发构建、source map、压缩的配对耗时变化分别为 -3.08%、-3.31%、
-2.02%，三个 95% 置信区间均不包含零。单线程仍分别慢 10.78%、7.36%、3.51%。
这确认了当前工作负载在 12/16 线程下的优势，不代表所有线程数或工作负载。
运行时默认线程数未改变。

**126 个进程、630 次构建**的输出哈希、模块数量和字节数量均一致，关闭成功，
没有线程创建失败或容量延迟。另有 18 次独立的冒烟构建，覆盖 React、普通 Three.js
和 Three.js-10x 在 16 线程下的三种模式。goexec 的 37 个常规测试、六个 Loom 模型、
格式和 Clippy 检查均通过；两个原生基准程序构建均无警告。

两个版本使用相同的 nightly-2026-04-16、Cargo.lock、编译配置和 QoS shim，
均设置 `CARGO_PROFILE_EXECUTOR_BENCH_DEBUG=1` 和
`CARGO_PROFILE_EXECUTOR_BENCH_STRIP=none`。每个进程预热两次，再保留三次测量。
每组打乱条件顺序，各条件内交替执行器顺序。统计使用下述配对进程组方法，
不删除异常值，也未进行多重比较校正。计时期间没有编译任务运行。
测试仅覆盖热文件缓存下的原生编译，不包含 Node/NAPI、JS 插件/loader 或 watch/HMR。
共享主机负载和系统调度仍是限制。原始结果和性能分析文件不加入 Git。

## Apple M3 Max 历史结果 — 2026-09-17

当前依赖的生产 Rust 源码与 2026-09-17 在 Apple M3 Max（12 个性能核心、4 个能效核心，
48 GiB 内存）上测量的最终版本一致。测量使用了本地 Cargo 路径；检出路径和 Git 依赖来源
可能改变二进制哈希。下列归档时间不是发布此次更新时对 Git 依赖版本重新测量的结果。

Three.js-10x，执行器和 Rayon 均为 **12 线程**，相同 USER_INITIATED QoS，
每个版本、每种条件测量 21 次：

| 模式 | Tokio 中位数 | 当前 goexec 中位数 | 相对 Tokio 的配对耗时变化 [95% CI] |
|---|---:|---:|---:|
| 开发构建 | 154.38 ms | 124.23 ms | -20.97% [-22.63, -18.92] |
| Source map | 283.03 ms | 253.10 ms | -9.91% [-11.52, -8.14] |
| 压缩 | 1156.97 ms | 1128.56 ms | -2.62% [-3.83, -1.22] |

耗时变化使用七组配对进程的中位数比值，置信区间使用 10,000 次 bootstrap 重采样，
因此不一定等于表中中位数的直接比值。8/12 线程调优阶段的全部 630 次构建中，
输出哈希、模块数量和字节数量一致，没有编译、关闭、线程创建错误或容量延迟。
所有版本编译时均设置 `CARGO_PROFILE_EXECUTOR_BENCH_DEBUG=1` 和
`CARGO_PROFILE_EXECUTOR_BENCH_STRIP=none`。复现时对上方两条构建命令使用相同设置，
运行时将线程数参数设为 `12`。测试未设置 CPU 亲和性。

这一差距同时包含线程数配置与执行器原有行为的影响。单独比较队列顺序改动时，
16 线程下开发构建比已包含管理逻辑回退及唤醒修复的初始 FIFO 版本快 2.7%，source map
快 3.0%。16 线程开发构建与 Tokio 持平，单线程仍较慢。运行时的默认线程数未改变，
这些数据不代表所有工作负载或 Node/NAPI 性能。

## Apple M5 Max 历史结果

以下归档结果来自 2026-09-17 的 Apple M5 Max，使用更新前固定的
`2faaeec15d1dd90fb7a25d9de58f29274cbeacbc`，不代表当前依赖。
16 线程 Three.js-10x 开发构建中，
旧 goexec 为 155.70 ms，优化版本为 98.24 ms，Tokio 为 104.91 ms。
这不是所有条件下的提升：单线程时优化版本仍比 Tokio 慢约 12%。
所有 1,365 次归档构建的输出哈希、模块数量和字节数量一致。

[英文说明](README.md)包含完整测试范围、相同 macOS QoS 的设置方式、统计方法、
原始数据及已知限制。归档数据是在发布本分支之前取得的，不是此次上传时重新测量的结果。
