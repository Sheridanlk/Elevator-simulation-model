try:
    import RPi.GPIO as GPIO
    IS_RPI = True
except (ImportError, RuntimeError):
    IS_RPI = False
    print("GPIO не найден. Работаем в режиме симуляции.")