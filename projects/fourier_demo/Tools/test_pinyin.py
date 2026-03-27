from pypinyin import lazy_pinyin
import sys

def contains_pinyin(text, target_pinyin_list):
    """
    Check if the target pinyin sequence exists in the text's pinyin.
    text: input string (e.g., "福利叶你好")
    target_pinyin_list: list of pinyin strings (e.g., ['fu', 'li', 'ye'])
    """
    text_pinyin = lazy_pinyin(text)
    print(f"Text: '{text}' -> Pinyin: {text_pinyin}")

    n = len(target_pinyin_list)
    for i in range(len(text_pinyin) - n + 1):
        if text_pinyin[i:i+n] == target_pinyin_list:
            return True
    return False

def test_matching():
    # Test Wake Words (Target: 傅里叶 -> fu li ye)
    wake_target = ['fu', 'li', 'ye']
    wake_tests = [
        ("傅里叶", True),
        ("福利叶", True),
        ("复利叶", True),
        ("富丽叶", True),
        ("你好", False),
        ("机器傅里叶", True)
    ]

    print("--- Testing Wake Word ---")
    for text, expected in wake_tests:
        result = contains_pinyin(text, wake_target)
        if result != expected:
            print(f"FAILED: '{text}'. Expected {expected}, got {result}")
            sys.exit(1)
        print(f"PASSED: '{text}'")

    # Test Wave (Target: 挥手 -> hui shou)
    wave_target = ['hui', 'shou']
    wave_tests = [
        ("挥手", True),
        ("回首", True), # Common homophone
        ("挥挥手", True), # Contains 'hui shou' ? wait, 'hui hui shou'
        ("招手", False)  # 'zhao shou' != 'hui shou'
    ]

    print("\n--- Testing Wave ---")
    # specific logic for "hui hui shou" which is ['hui', 'hui', 'shou']
    # If we look for ['hui', 'shou'], 'hui hui shou' might fail if we don't skip the middle 'hui'.
    # But usually "挥手" is the core command. Let's see if "回首" works.

    for text, expected in wave_tests:
        # Note: '挥挥手' -> ['hui', 'hui', 'shou']. Does it contain ['hui', 'shou']? Yes, at index 1.
        result = contains_pinyin(text, wave_target)
        if result != expected:
            print(f"FAILED: '{text}'. Expected {expected}, got {result}")
            # Don't exit here, just log, maybe our logic needs adjustment
        else:
            print(f"PASSED: '{text}'")

if __name__ == "__main__":
    test_matching()
