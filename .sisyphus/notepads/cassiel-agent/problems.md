## Cassiel Agent — Problems

### 🔒 Blocker: Phase 4.5 — Win11 VM Clean Verification
- **Task**: 在无 Python 的干净 Win11 虚拟机中运行 .exe，验证全流程
- **Why blocked**: 当前开发环境不支持 Win11 VM 创建，且 pip 依赖未安装
- **What's needed**: 
  1. `pip install playwright nicegui modelscope-agent pydantic` (需要外网)
  2. `playwright install chromium`
  3. 运行 Phase 0 spikes 验证
  4. `pyinstaller cassiel-agent.spec` 构建 .exe
  5. 在 Win11 VM 中测试 .exe
- **Mitigation**: 配置文件已就绪 (cassiel-agent.spec, build_nuitka.py, installer.nsi)，用户本地运行即可
- **Status**: 等待本地环境
