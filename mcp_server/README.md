# MCP Order Service

基于 FastMCP 的订单服务 MCP Server。目前只初始化服务，暂未注册工具。

在仓库根目录安装依赖并启动：

```bash
pip install -r mcp_server/requirements.txt
mcp dev mcp_server/main.py
```

也可以使用 Python 模块方式启动：

```bash
python -m mcp_server.main
```

`python -m` 方式启动时会通过 stdio 运行，供 backend MCP client 子进程连接。
