"""设备端MCP工具执行器"""

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from ..base import ToolType, ToolDefinition, ToolExecutor
from plugins_func.register import Action, ActionResponse
from .mcp_handler import call_mcp_tool


class DeviceMCPExecutor(ToolExecutor):
    """设备端MCP工具执行器"""

    def __init__(self, conn):
        self.conn = conn

    async def execute(
        self, conn: "ConnectionHandler", tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """执行设备端MCP工具"""
        if not hasattr(conn, "mcp_client") or not conn.mcp_client:
            return ActionResponse(
                action=Action.ERROR,
                response="设备端MCP客户端未初始化",
            )

        if not await conn.mcp_client.is_ready():
            return ActionResponse(
                action=Action.ERROR,
                response="设备端MCP客户端未准备就绪",
            )

        try:
            # 转换参数为JSON字符串
            import json

            args_str = json.dumps(arguments) if arguments else "{}"

            # 调用设备端MCP工具
            result = await call_mcp_tool(conn, conn.mcp_client, tool_name, args_str)

            resultJson = None
            if isinstance(result, str):
                try:
                    resultJson = json.loads(result)
                except Exception as e:
                    pass

            # 视觉大模型不经过二次LLM处理
            if (
                resultJson is not None
                and isinstance(resultJson, dict)
                and "action" in resultJson
            ):
                if (
                    tool_name in ("self.camera.take_photo", "self_camera_take_photo")
                    and resultJson.get("success") is True
                    and resultJson.get("action") == "RESPONSE"
                ):
                    # AI検査員: 初回撮影の位置情報を用いて再撮影する
                    import asyncio
                    import logging
                    motion_logger = logging.getLogger(__name__)

                    first_raw = str(resultJson.get("response", "")).strip()
                    if first_raw.startswith("```"):
                        first_raw = first_raw.split("\n", 1)[-1]
                        first_raw = first_raw.rsplit("```", 1)[0].strip()

                    try:
                        first_data = json.loads(first_raw)
                    except (ValueError, TypeError):
                        first_data = {}

                    if isinstance(first_data, dict) and first_data.get("phase") == "position":
                        horizontal = first_data.get("horizontal")
                        detected = first_data.get("vehicle_detected") is True
                        motion_logger.info(
                            "AI検査員: 位置認識 detected=%s horizontal=%s vertical=%s",
                            detected, horizontal, first_data.get("vertical")
                        )

                        # 補正は一度だけ。上下は現時点で動かさない。
                        # 左右の符号は実機撮影結果で検証する。
                        yaw = {"left": -15, "right": 15}.get(horizontal, 0)

                        if detected and yaw:
                            try:
                                servo_result = await call_mcp_tool(
                                    conn, conn.mcp_client,
                                    "self_robot_set_head_angles",
                                    json.dumps({
                                        "yaw": yaw,
                                        "pitch": -9999,
                                        "speed": 200
                                    })
                                )
                                motion_logger.info(
                                    "AI検査員: 位置補正 yaw=%s MCP=%s",
                                    yaw, servo_result
                                )
                                await asyncio.sleep(1.5)
                            except Exception as e:
                                motion_logger.warning(
                                    "AI検査員: 位置補正失敗: %s", e
                                )

                        # 中央・位置不明の場合も再撮影し、通常の検査へ進む。
                        try:
                            second = await call_mcp_tool(
                                conn, conn.mcp_client,
                                "self_camera_take_photo",
                                json.dumps({
                                    "question": "目の前のミニカーを撮影し、外観を検査してください。"
                                }, ensure_ascii=False)
                            )
                            second_data = json.loads(second)
                            if (
                                not isinstance(second_data, dict)
                                or second_data.get("success") is not True
                                or second_data.get("action") != "RESPONSE"
                            ):
                                raise ValueError("再撮影の結果が不正です")
                            resultJson = second_data
                            motion_logger.info("AI検査員: 再撮影・外観検査完了")
                        except Exception as e:
                            motion_logger.error("AI検査員: 再撮影失敗: %s", e)
                            return ActionResponse(
                                action=Action.REQLLM,
                                result=(
                                    "再撮影に失敗したため、外観検査の合否は判定できません。"
                                    "この内容を短く日本語で説明してください。"
                                    "再撮影は指示しないでください。"
                                )
                            )

                    # AI検査員: VLMのOK判定を物理動作に反映
                    raw = str(resultJson.get("response", "")).strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[-1]
                        raw = raw.rsplit("```", 1)[0].strip()
                    try:
                        inspection = json.loads(raw)
                        if isinstance(inspection, dict):
                            judgment = inspection.get("judgment")
                            if judgment in ("OK", "NG"):
                                await self._move_head_for_judgment(conn, judgment)
                    except json.JSONDecodeError:
                        pass

                    return ActionResponse(
                        action=Action.REQLLM,
                        result=(
                            "以下はカメラで撮影した画像の検査結果です。"
                            "観察できた事実と合否の理由を日本語で簡潔に説明してください。"
                            "画像にない情報を推測しないでください。"
                            "再撮影は不要です。\n"
                            + str(resultJson.get("response", ""))
                        ),
                    )
                return ActionResponse(
                    action=Action[resultJson["action"]],
                    response=resultJson.get("response", ""),
                )

            return ActionResponse(action=Action.REQLLM, result=str(result))

        except ValueError as e:
            return ActionResponse(action=Action.NOTFOUND, response=str(e))
        except Exception as e:
            return ActionResponse(action=Action.ERROR, response=str(e))

    async def _move_head_for_judgment(self, conn, judgment):
        """画像判定に応じて首を動かす。"""
        import asyncio
        import json
        import logging

        logger = logging.getLogger(__name__)

        if judgment == "OK":
            positions = [
                {"yaw": -9999, "pitch": 20, "speed": 200},
                {"yaw": -9999, "pitch": 0, "speed": 200},
            ]
        elif judgment == "NG":
            positions = [
                {"yaw": -15, "pitch": -9999, "speed": 200},
                {"yaw": 15, "pitch": -9999, "speed": 200},
                {"yaw": 0, "pitch": -9999, "speed": 200},
            ]
        else:
            return

        try:
            for position in positions:
                logger.info(
                    "AI検査員: %s首振り指示: %s", judgment, position
                )
                result = await call_mcp_tool(
                    conn,
                    conn.mcp_client,
                    "self_robot_set_head_angles",
                    json.dumps(position),
                )
                logger.info("AI検査員: サーボMCP応答: %s", result)
                await asyncio.sleep(0.9)

            logger.info("AI検査員: %s首振り命令完了", judgment)
        except Exception as e:
            logger.warning("AI検査員: 首振り失敗: %s", e)

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """获取所有设备端MCP工具"""
        if not hasattr(self.conn, "mcp_client") or not self.conn.mcp_client:
            return {}

        tools = {}
        mcp_tools = self.conn.mcp_client.get_available_tools()

        for tool in mcp_tools:
            func_def = tool.get("function", {})
            tool_name = func_def.get("name", "")

            if tool_name:
                tools[tool_name] = ToolDefinition(
                    name=tool_name, description=tool, tool_type=ToolType.DEVICE_MCP
                )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定的设备端MCP工具"""
        if not hasattr(self.conn, "mcp_client") or not self.conn.mcp_client:
            return False

        return self.conn.mcp_client.has_tool(tool_name)
