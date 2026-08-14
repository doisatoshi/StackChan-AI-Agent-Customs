/*
 * image.h
 *
 * PNG avatar implementation for StackChan AI.AGENT.
 *
 * Part of the StackChan-AI-Agent-Customs project.
 * https://github.com/doisatoshi/StackChan-AI-Agent-Customs
 */

#pragma once

#include "../../avatar/avatar.h"

#include <lvgl.h>
#include <smooth_lvgl.hpp>
#include <memory>

namespace stackchan::avatar {

/**
 * @brief PNG画像を使用するアバター
 *
 * 画像を切り替えることで
 * ・通常
 * ・まばたき
 * ・口パク
 * ・呼吸
 * を表現する。
 */
class ImageAvatar : public Avatar {
public:

    /**
     * @brief アバター初期化
     *
     * @param parent 描画先
     * @param font 吹き出し用フォント（現在未使用）
     */
    void init(
        lv_obj_t* parent,
        const lv_font_t* font = &lv_font_montserrat_16
    );

    /**
     * @brief 毎フレーム呼ばれる更新処理
     *
     * ・まばたき
     * ・口パク
     * ・呼吸
     *
     * をここで制御する。
     */
    void update() override;

    /**
     * @brief 発話開始・終了を通知する
     *
     * true  = speaking.png
     * false = neutral.png
     */
    void setSpeaking(bool speaking);

    /**
     * @brief 表示パネル取得
     */
    uitk::lvgl_cpp::Container* getPanel() const;

    /**
     * @brief ImageAvatarには可動パーツが存在しない
     */
    bool hasMovableFeatures() const override
    {
        return false;
    }

private:

    //--------------------------------------------------
    // 画像切替関数
    //--------------------------------------------------

    /// 通常顔
    void showNeutral();

    /// まばたき
    void showBlink();

    /// 口パク
    void showSpeaking();

    /// 呼吸
    void showBreath();

    //--------------------------------------------------
    // アニメーション内部処理
    //--------------------------------------------------

    /// 一定時間ごとにまばたきを行う
    void updateBlink();

    /// 発話中の口パクを行う
    void updateSpeaking();

    /// 待機中の呼吸表現を行う
    void updateBreath();

    //--------------------------------------------------
    // UI部品
    //--------------------------------------------------

    /// アバター全体のパネル
    std::unique_ptr<uitk::lvgl_cpp::Container> _panel;

    /// 表示画像
    std::unique_ptr<uitk::lvgl_cpp::Image> _image;

    //--------------------------------------------------
    // 画像データ
    //--------------------------------------------------

    /// 通常顔
    lv_image_dsc_t _neutral_image{};

    /// まばたき
    lv_image_dsc_t _blink_image{};

    /// 口パク
    lv_image_dsc_t _speaking_image{};

    /// 呼吸
    lv_image_dsc_t _breath_image{};

    //--------------------------------------------------
    // 状態管理
    //--------------------------------------------------

    /// 現在発話中か
    bool _is_speaking = false;

    /// 現在まばたき中か
    bool _is_blinking = false;

    /// 呼吸画像を表示中か
    bool _breath_phase = false;

    //--------------------------------------------------
    // タイマー
    //--------------------------------------------------

    /// 前回まばたきした時刻
    uint32_t _last_blink_tick = 0;

    /// 前回口パク切替時刻
    uint32_t _last_speaking_tick = 0;

    /// 前回呼吸更新時刻
    uint32_t _last_breath_tick = 0;

    /// まばたき開始時刻
    uint32_t _blink_start_tick = 0;
};

} // namespace stackchan::avatar