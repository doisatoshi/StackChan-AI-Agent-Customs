import openai
import json
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.vllm.base import VLLMProviderBase

TAG = __name__
logger = setup_logging()


class VLLMProvider(VLLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.api_key = config.get("api_key")
        if "base_url" in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")

        param_defaults = {
            "max_tokens": (500, int),
            "temperature": (0.7, lambda x: round(float(x), 1)),
            "top_p": (1.0, lambda x: round(float(x), 1)),
        }

        for param, (default, converter) in param_defaults.items():
            value = config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else default,
                )
            except (ValueError, TypeError):
                setattr(self, param, default)

        model_key_msg = check_model_key("VLLM", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def response(self, question, base64_image):
        if "[POSITION]" in question:
            question = (
                "画像内にミニカーがあるか確認してください。"
                "ミニカーの中心位置を画像全体の9分割で判定してください。"
                "horizontalはleft、center、rightのいずれか、"
                "verticalはtop、center、bottomのいずれかです。"
                "車両が見つからない場合はvehicle_detectedをfalseにしてください。"
                "回答は次の4項目のJSONのみとしてください。"
                "phase、vehicle_detected、horizontal、vertical。"
                "phaseは必ずpositionとしてください。"
                "位置が不明な場合はhorizontalとverticalをunknownにしてください。"
                "外観検査やOK・NG判定はまだ行わないでください。"
            )
        else:
            question = (
                "あなたはミニカーの外観検査員です。画像を観察し、検査条件と照合してください。"
                "合格条件は、車種がSUV、ボディ色がオレンジ、屋根色が白であることです。"
                "3条件すべてを確認できた場合のみOK、それ以外や判別不能の場合はNGです。"
                "傷やへこみは今回の判定対象ではありません。"
                "画像で実際に確認できた内容だけを使用し、推測しないでください。"
                "回答はJSONのみとし、vehicle_type、body_color、roof_color、"
                "judgment、reasonの5項目を含めてください。"
                "各項目の値は日本語で記述し、judgmentだけはOKまたはNGにしてください。"
                "確認できない項目は「不明」としてください。"
                "reasonは判定理由を日本語で一文にまとめてください。"
            )
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ]

            response = self.client.chat.completions.create(
                model=self.model_name, messages=messages, stream=False
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")
            raise
