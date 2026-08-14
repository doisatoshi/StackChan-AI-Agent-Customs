/*
 * image.cpp
 *
 * PNG avatar implementation for StackChan AI.AGENT.
 *
 * Part of the StackChan-AI-Agent-Customs project.
 * https://github.com/doisatoshi/StackChan-AI-Agent-Customs
 */

#include "image.h"

// assets.binに格納されたPNG画像を取得するために使用する
#include <assets/assets.h>

// LVGLのC++ラッパークラスを短い名前で使用できるようにする
using namespace uitk::lvgl_cpp;

// ImageAvatarを名前空間なしで記述できるようにする
using namespace stackchan::avatar;

namespace {

// 通常時にまばたきする間隔
// 現在は4秒ごとに設定する
constexpr uint32_t BLINK_INTERVAL_MS = 4000;

// 目を閉じている時間
// 140ミリ秒だけblink.pngを表示する
constexpr uint32_t BLINK_DURATION_MS = 140;

// 発話中に口の開閉を切り替える間隔
// 180ミリ秒ごとにneutral.pngとspeaking.pngを交互表示する
constexpr uint32_t SPEAKING_INTERVAL_MS = 180;

// 呼吸画像を切り替える間隔
// 900ミリ秒ごとにneutral.pngとbreath.pngを交互表示する
constexpr uint32_t BREATH_INTERVAL_MS = 900;

}  // namespace

/**
 * @brief ImageAvatarを初期化する
 */
void ImageAvatar::init(lv_obj_t* parent, const lv_font_t* font)
{
    // 現段階では吹き出しを使わないため、fontは未使用とする
    (void)font;

    // StackChanの画面全体を覆う320×240ピクセルのパネルを作成する
    _panel = std::make_unique<Container>(parent);

    // パネルを画面中央へ配置する
    _panel->align(LV_ALIGN_CENTER, 0, 0);

    // StackChanのディスプレイサイズに合わせる
    _panel->setSize(320, 240);

    // 角丸を無効にする
    _panel->setRadius(0);

    // 枠線を非表示にする
    _panel->setBorderWidth(0);

    // PNG画像の周囲は黒背景にする
    _panel->setBgColor(lv_color_black());

    // パネルがスクロールしないようにする
    _panel->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // 通常顔のPNG画像をassets.binから取得する
    _neutral_image = assets::get_image("neutral.png");

    // まばたき用のPNG画像をassets.binから取得する
    _blink_image = assets::get_image("blink.png");

    // 口を開いたPNG画像をassets.binから取得する
    _speaking_image = assets::get_image("speaking.png");

    // 呼吸表現用のPNG画像をassets.binから取得する
    _breath_image = assets::get_image("breath.png");

    // 画像を表示するためのLVGL Imageオブジェクトを作成する
    _image = std::make_unique<Image>(*_panel);

    // 顔画像をパネル中央へ配置する
    _image->align(LV_ALIGN_CENTER, 0, 0);

    // 起動直後は通常顔を表示する
    showNeutral();

    // 現在時刻を取得する
    const uint32_t now = lv_tick_get();

    // まばたきタイマーの基準時刻を設定する
    _last_blink_tick = now;

    // 口パクタイマーの基準時刻を設定する
    _last_speaking_tick = now;

    // 呼吸タイマーの基準時刻を設定する
    _last_breath_tick = now;

    // 起動時は発話していない状態とする
    _is_speaking = false;

    // 起動時はまばたきしていない状態とする
    _is_blinking = false;

    // 起動時は通常位置の画像を表示する
    _breath_phase = false;
}

/**
 * @brief ImageAvatarのアニメーションを更新する
 *
 * StackChan::update()から繰り返し呼び出される。
 */
void ImageAvatar::update()
{
    // Avatar基底クラスの更新処理も維持する
    Avatar::update();

    // 発話中は口パクを最優先する
    if (_is_speaking) {
        updateSpeaking();
        return;
    }

    // 発話していないときは、まばたきを更新する
    updateBlink();

    // まばたき中は呼吸画像へ切り替えない
    if (_is_blinking) {
        return;
    }

    // 発話中でもまばたき中でもない場合は呼吸を更新する
    updateBreath();
}

/**
 * @brief 発話開始または発話終了をImageAvatarへ通知する
 */
void ImageAvatar::setSpeaking(bool speaking)
{
    // 発話状態に変化がない場合は何もしない
    if (_is_speaking == speaking) {
        return;
    }

    // 新しい発話状態を保存する
    _is_speaking = speaking;

    // 現在時刻を口パクタイマーの基準にする
    _last_speaking_tick = lv_tick_get();

    // 発話開始時の処理
    if (_is_speaking) {
        // まばたき中だった場合は解除する
        _is_blinking = false;

        // 最初から口を開けた画像を表示する
        showSpeaking();

        // 発話開始後はここで終了する
        return;
    }

    // 発話が終了したら通常顔へ戻す
    showNeutral();

    // 呼吸アニメーションも通常側から再開する
    _breath_phase = false;

    // 呼吸タイマーを現在時刻から再スタートする
    _last_breath_tick = lv_tick_get();

    // まばたきタイマーも現在時刻から再スタートする
    _last_blink_tick = lv_tick_get();
}

/**
 * @brief 通常顔を表示する
 */
void ImageAvatar::showNeutral()
{
    // Imageオブジェクトが作成されていない場合は何もしない
    if (!_image) {
        return;
    }

    // neutral.pngが正常に読み込まれている場合だけ表示する
    if (_neutral_image.data_size != 0) {
        _image->setSrc(&_neutral_image);
    }
}

/**
 * @brief まばたき画像を表示する
 */
void ImageAvatar::showBlink()
{
    // Imageオブジェクトが作成されていない場合は何もしない
    if (!_image) {
        return;
    }

    // blink.pngが正常に読み込まれている場合だけ表示する
    if (_blink_image.data_size != 0) {
        _image->setSrc(&_blink_image);
    }
}

/**
 * @brief 発話中の口を開いた画像を表示する
 */
void ImageAvatar::showSpeaking()
{
    // Imageオブジェクトが作成されていない場合は何もしない
    if (!_image) {
        return;
    }

    // speaking.pngが正常に読み込まれている場合だけ表示する
    if (_speaking_image.data_size != 0) {
        _image->setSrc(&_speaking_image);
    }
}

/**
 * @brief 呼吸表現用の画像を表示する
 */
void ImageAvatar::showBreath()
{
    // Imageオブジェクトが作成されていない場合は何もしない
    if (!_image) {
        return;
    }

    // breath.pngが正常に読み込まれている場合だけ表示する
    if (_breath_image.data_size != 0) {
        _image->setSrc(&_breath_image);
    }
}

/**
 * @brief まばたきアニメーションを更新する
 */
void ImageAvatar::updateBlink()
{
    // 現在時刻を取得する
    const uint32_t now = lv_tick_get();

    // 現在まばたき中の場合
    if (_is_blinking) {
        // 目を閉じてから所定時間が経過したか確認する
        if (now - _blink_start_tick >= BLINK_DURATION_MS) {
            // まばたきを終了する
            _is_blinking = false;

            // 呼吸画像表示中なら呼吸画像へ戻す
            if (_breath_phase) {
                showBreath();
            } else {
                // 通常側なら通常画像へ戻す
                showNeutral();
            }
        }

        // まばたき中は新しいまばたきを開始しない
        return;
    }

    // 前回のまばたきから4秒以上経過したか確認する
    if (now - _last_blink_tick >= BLINK_INTERVAL_MS) {
        // まばたき状態を開始する
        _is_blinking = true;

        // まばたきを開始した時刻を保存する
        _blink_start_tick = now;

        // 前回まばたき時刻を更新する
        _last_blink_tick = now;

        // 目を閉じた画像へ切り替える
        showBlink();
    }
}

/**
 * @brief 発話中の口パクを更新する
 */
void ImageAvatar::updateSpeaking()
{
    // 念のため、発話中でない場合は何もしない
    if (!_is_speaking) {
        return;
    }

    // 現在時刻を取得する
    const uint32_t now = lv_tick_get();

    // 前回の画像切り替えから180ミリ秒未満なら何もしない
    if (now - _last_speaking_tick < SPEAKING_INTERVAL_MS) {
        return;
    }

    // 口パク画像の切り替え時刻を更新する
    _last_speaking_tick = now;

    // 呼吸フェーズ用フラグを口パクの開閉状態として一時的に利用する
    _breath_phase = !_breath_phase;

    // 開く側のタイミングではspeaking.pngを表示する
    if (_breath_phase) {
        showSpeaking();
    } else {
        // 閉じる側のタイミングではneutral.pngを表示する
        showNeutral();
    }
}

/**
 * @brief 待機中の呼吸アニメーションを更新する
 */
void ImageAvatar::updateBreath()
{
    // 現在時刻を取得する
    const uint32_t now = lv_tick_get();

    // 前回の切り替えから900ミリ秒未満なら何もしない
    if (now - _last_breath_tick < BREATH_INTERVAL_MS) {
        return;
    }

    // 呼吸画像の切り替え時刻を更新する
    _last_breath_tick = now;

    // 通常画像と呼吸画像の表示状態を反転する
    _breath_phase = !_breath_phase;

    // 呼吸側のフェーズでは8ピクセル上へ移動した画像を表示する
    if (_breath_phase) {
        showBreath();
    } else {
        // 通常側のフェーズでは通常画像へ戻す
        showNeutral();
    }
}

/**
 * @brief ImageAvatarの表示パネルを取得する
 */
Container* ImageAvatar::getPanel() const
{
    // パネルが作成されている場合は、そのポインタを返す
    if (_panel) {
        return _panel.get();
    }

    // パネルが存在しない場合はnullptrを返す
    return nullptr;
}