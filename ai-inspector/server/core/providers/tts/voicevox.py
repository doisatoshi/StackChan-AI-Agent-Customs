#VOICEVOX用TTSプロバイダ

#処理の流れ：
#1. /audio_queryへ文章と話者IDを送信
#2. 返されたAudioQueryへ速度・音量などを設定
#3. /synthesisへAudioQueryを送信
#4. WAV音声を受け取る
#5. xiaozhi-serverの基底クラスへWAVデータを返す

import asyncio
import json
import os
import uuid

from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    """
    VOICEVOX Engineを利用して音声を生成するTTSプロバイダ。

    xiaozhi-serverから渡された文章をVOICEVOXへ送信し、
    生成されたWAVデータを返す。
    """

    def __init__(self, config, delete_audio_file):
        """
        VOICEVOXプロバイダを初期化する。

        configで使用する主な項目：

        base_url:
            VOICEVOX EngineのURL。
            DockerからMac上のVOICEVOXへ接続する場合は
            http://host.docker.internal:50021 を使用する。

        speaker:
            VOICEVOXの話者・スタイルID。
            ずんだもんのノーマルは通常3。

        speed_scale:
            話速。標準は1.0。

        pitch_scale:
            音高。標準は0.0。

        intonation_scale:
            抑揚。標準は1.0。

        volume_scale:
            音量。標準は1.0。
        """

        # TTSProviderBaseの初期化処理を実行する。
        super().__init__(config, delete_audio_file)

        # hostまたはbase_urlのどちらの設定名にも対応する。
        self.base_url = config.get(
            "base_url",
            config.get("host", "http://host.docker.internal:50021"),
        ).rstrip("/")

        # 使用するVOICEVOXの話者・スタイルIDを取得する。
        # ずんだもんのノーマルは通常speaker=3。
        self.speaker = int(config.get("speaker", 3))

        # VOICEVOXへのHTTP接続タイムアウト秒数を取得する。
        self.request_timeout = int(config.get("request_timeout", 30))

        # 話す速さを取得する。
        # 1.0が標準、1.2なら20％速くなる。
        self.speed_scale = float(config.get("speed_scale", 1.0))

        # 声の高さを取得する。
        # 0.0が標準。
        self.pitch_scale = float(config.get("pitch_scale", 0.0))

        # 抑揚の強さを取得する。
        # 1.0が標準。
        self.intonation_scale = float(
            config.get("intonation_scale", 1.0)
        )

        # 音量を取得する。
        # 1.0が標準。
        self.volume_scale = float(config.get("volume_scale", 1.0))

        # 音声開始前の無音時間を取得する。
        self.pre_phoneme_length = float(
            config.get("pre_phoneme_length", 0.1)
        )

        # 音声終了後の無音時間を取得する。
        self.post_phoneme_length = float(
            config.get("post_phoneme_length", 0.1)
        )

        # VOICEVOXが返す音声形式はWAV。
        self.audio_file_type = "wav"

    def generate_filename(self, extension=".wav"):
        """
        音声をファイルへ保存する場合の一時ファイル名を生成する。
        """

        # 出力ディレクトリと重複しないUUIDを組み合わせる。
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        """
        文章をVOICEVOXで音声へ変換する。

        output_fileが指定された場合：
            WAVファイルへ保存する。

        output_fileがNoneの場合：
            WAVのバイナリデータを返す。
        """

        try:
            # urllibは同期処理なので、別スレッドで実行して
            # asyncioのイベントループを止めないようにする。
            audio_bytes = await asyncio.to_thread(
                self._synthesize,
                text,
            )

            # 出力先ファイルが指定されている場合。
            if output_file:
                # 保存先ディレクトリを作成する。
                output_dir = os.path.dirname(output_file)

                # output_fileにディレクトリ部分がある場合だけ作成する。
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)

                # 取得したWAVデータをファイルへ保存する。
                with open(output_file, "wb") as audio_file:
                    audio_file.write(audio_bytes)

                # ファイル保存時は戻り値を使用しない。
                return None

            # ファイル保存しない場合はWAVデータをそのまま返す。
            return audio_bytes

        except Exception as error:
            # 基底クラス側で再試行できるように例外を送出する。
            raise Exception(
                f"VOICEVOX TTSリクエスト失敗: {error}"
            ) from error

    def _synthesize(self, text):
        """
        VOICEVOX APIを同期的に呼び出してWAVデータを取得する。

        1. audio_queryを作成
        2. 音声パラメータを調整
        3. synthesisでWAVを生成
        """

        # --------------------------------------------------
        # 1. audio_queryを作成する
        # --------------------------------------------------

        # URLへ渡すクエリパラメータを作成する。
        query_parameters = urlencode(
            {
                "text": text,
                "speaker": self.speaker,
            }
        )

        # audio_query APIのURLを作成する。
        audio_query_url = (
            f"{self.base_url}/audio_query?{query_parameters}"
        )

        # POSTリクエストを作成する。
        # VOICEVOXのaudio_queryは本文なしのPOSTで呼び出せる。
        audio_query_request = Request(
            audio_query_url,
            data=b"",
            method="POST",
        )

        try:
            # VOICEVOXへaudio_queryリクエストを送信する。
            with urlopen(
                audio_query_request,
                timeout=self.request_timeout,
            ) as response:
                # JSONレスポンスを読み込む。
                audio_query = json.loads(
                    response.read().decode("utf-8")
                )

        except HTTPError as error:
            # HTTPエラー時はVOICEVOXの応答本文も取得する。
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                "VOICEVOX audio_queryエラー: "
                f"HTTP {error.code}, {error_body}"
            ) from error

        except URLError as error:
            # VOICEVOX Engineへ接続できなかった場合。
            raise RuntimeError(
                "VOICEVOX Engineへ接続できません: "
                f"{self.base_url}, {error.reason}"
            ) from error

        # --------------------------------------------------
        # 2. 音声パラメータを調整する
        # --------------------------------------------------

        # 話す速さを設定する。
        audio_query["speedScale"] = self.speed_scale

        # 声の高さを設定する。
        audio_query["pitchScale"] = self.pitch_scale

        # 抑揚を設定する。
        audio_query["intonationScale"] = self.intonation_scale

        # 音量を設定する。
        audio_query["volumeScale"] = self.volume_scale

        # 発話前の無音時間を設定する。
        audio_query["prePhonemeLength"] = self.pre_phoneme_length

        # 発話後の無音時間を設定する。
        audio_query["postPhonemeLength"] = self.post_phoneme_length

        # モノラル音声を指定する。
        audio_query["outputStereo"] = False

        # --------------------------------------------------
        # 3. synthesisでWAV音声を生成する
        # --------------------------------------------------

        # synthesis APIへ渡す話者IDをURLパラメータにする。
        synthesis_parameters = urlencode(
            {
                "speaker": self.speaker,
            }
        )

        # synthesis APIのURLを作成する。
        synthesis_url = (
            f"{self.base_url}/synthesis?{synthesis_parameters}"
        )

        # AudioQueryをJSON形式へ変換する。
        synthesis_body = json.dumps(
            audio_query,
            ensure_ascii=False,
        ).encode("utf-8")

        # synthesis用のPOSTリクエストを作成する。
        synthesis_request = Request(
            synthesis_url,
            data=synthesis_body,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            # VOICEVOXへ音声合成リクエストを送信する。
            with urlopen(
                synthesis_request,
                timeout=self.request_timeout,
            ) as response:
                # 生成されたWAVデータを返す。
                return response.read()

        except HTTPError as error:
            # 音声合成時のHTTPエラー本文を取得する。
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                "VOICEVOX synthesisエラー: "
                f"HTTP {error.code}, {error_body}"
            ) from error

        except URLError as error:
            # VOICEVOX Engineとの通信に失敗した場合。
            raise RuntimeError(
                "VOICEVOX synthesis接続エラー: "
                f"{self.base_url}, {error.reason}"
            ) from error