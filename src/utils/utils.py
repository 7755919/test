
# src/device/utils.py
import cv2
import numpy as np
import time
from skimage.metrics import structural_similarity as ssim

def wait_for_screen_stable(device_state, timeout=10, threshold=0.90, interval=0.1, max_checks=1):
    """
    等待設備屏幕穩定

    :param device_state: 設備狀態對象
    :param timeout: 超時時間（秒）
    :param threshold: 圖像相似度閾值
    :param interval: 截圖間隔時間（秒）
    :param max_checks: 連續穩定畫面的次數
    :return: 如果屏幕穩定則返回True，超時返回False
    """
    start_time = time.time()
    last_screenshot = None
    stable_count = 0
    change_logged = False
    
    # 預先取得 logger 和計算結束時間，避免重複查找屬性
    logger = device_state.logger
    end_time = start_time + timeout

    while time.time() < end_time:
        screenshot = device_state.take_screenshot()
        if screenshot is None:
            time.sleep(interval)
            continue

        # 將PIL圖像轉換為OpenCV格式（優化：直接使用 np.asarray 避免複製）
        frame = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2GRAY)

        if last_screenshot is not None:
            # 計算SSIM（優化：不需要 full=True 返回的完整差異圖）
            score = ssim(last_screenshot, frame, full=False)
            
            if score > threshold:
                stable_count += 1
                change_logged = False
                
                if stable_count >= max_checks:
                    logger.info(f"畫面已穩定 (穩定度: {score:.3f})")
                    return True
            else:
                if not change_logged:
                    logger.info(f"畫面特效持續中... (穩定度: {score:.3f})")
                    change_logged = True
                stable_count = 0
        
        last_screenshot = frame
        time.sleep(interval)

    logger.warning("等待畫面穩定超時")
    return False