"""
gestures.py — Распознавание жестов через MediaPipe.
Работает на Linux и Windows.
"""
import cv2
import mediapipe as mp
import threading

class GestureDetector:
    def __init__(self, voice=None, callback=None):
        self.voice = voice
        self.callback = callback
        self.running = False
        self._thread = None
        self.cap = None
        
        # Инициализация MediaPipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_drawing = mp.solutions.drawing_utils

    def start(self):
        if self.running:
            return "✋ Жесты уже работают"
        
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            return "❌ Камера не доступна"
            
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return "✋ Распознавание жестов активировано"

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        return "⏹️ Жесты выключены"

    def _loop(self):
        import time
        import cv2
        import mediapipe as mp

        # Переменные для фильтрации
        current_gesture = None
        gesture_counter = 0
        last_trigger_time = 0
        cooldown = 2.5
        hold_frames = 10  # Жест должен продержаться 10 кадров (~0.3 сек)

        # Переменные для отрисовки
        mp_drawing = mp.solutions.drawing_utils
        mp_hands = mp.solutions.hands

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Отражаем кадр (как зеркало)
            frame = cv2.flip(frame, 1)
            
            # Конвертация в RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = self.hands.process(rgb)

            detected_gesture = None

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Рисуем скелет
                    mp_drawing.draw_landmarks(
                        frame, hand_landmarks, mp_hands.HAND_CONNECTIONS
                    )
                    
                    # Детектим жест
                    detected_gesture = self._detect_gesture(hand_landmarks)
                    
                    # Пишем название жеста на экране
                    if detected_gesture:
                        cv2.putText(frame, f"Gesture: {detected_gesture.upper()}", 
                                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                                    1, (0, 255, 0), 2)

            # --- ЛОГИКА ФИЛЬТРАЦИИ ---
            now = time.time()
            if detected_gesture:
                if detected_gesture == current_gesture:
                    gesture_counter += 1
                else:
                    current_gesture = detected_gesture
                    gesture_counter = 1

                # Если жест стабилен и прошло время кулдауна
                if gesture_counter == hold_frames and (now - last_trigger_time > cooldown):
                    print(f"✋ Сработал жест: {current_gesture}")
                    if self.callback:
                        self.callback(current_gesture)
                    last_trigger_time = now
                    gesture_counter = 0
            else:
                current_gesture = None
                gesture_counter = 0

            # Показываем окно (ВАЖНО: для отладки)
            cv2.imshow("Fitz Vision (Q - Exit)", frame)
            
            # Выход по кнопке Q
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.stop()
                break

            time.sleep(0.01)

        cv2.destroyAllWindows()

    def _detect_gesture(self, landmarks):
        """
        Упрощённый анализатор: только кулак и ладонь.
        """
        lm = landmarks.landmark
        tips = [8, 12, 16, 20] # Указательный, средний, безымянный, мизинец
        joints = [5, 9, 13, 17]
        
        fingers_up = 0
        
        # Проверяем 4 пальца (большой не считаем, чтобы не путаться)
        for i in range(4):
            if lm[tips[i]].y < lm[joints[i]].y:
                fingers_up += 1

        # Если все 4 пальца подняты (ладонь)
        if fingers_up == 4:
            return "open_hand"
        
        # Если все 4 пальца согнуты (кулак)
        if fingers_up == 0:
            return "fist"

        return None