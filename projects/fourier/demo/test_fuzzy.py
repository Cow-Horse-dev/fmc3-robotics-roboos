from pypinyin import lazy_pinyin
import sys

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def check_pinyin_match(text_pinyin, target_pinyin, threshold=1):
    n = len(target_pinyin)
    # Check windows of size n-1 to n+1
    # n-1: allow 1 deletion
    # n: allow substitutions
    # n+1: allow 1 insertion
    for length in range(max(1, n - 1), n + 2):
        for i in range(len(text_pinyin) - length + 1):
            sub_segment = text_pinyin[i : i + length]
            dist = levenshtein_distance(sub_segment, target_pinyin)
            if dist <= threshold:
                return True, dist
    return False, -1

def run_test():
    target = ['fu', 'li', 'ye'] # 傅里叶

    test_cases = [
        ("傅里叶", True),     # Perfect match (dist=0)
        ("福利叶", True),     # Homophone match (dist=0)
        ("傅叶", True),       # Fast speech: skipped "li" (dist=1, deletion)
        ("傅立叶", True),     # Homophone (dist=0)
        ("傅里里叶", True),   # Stutter/insertion (dist=1)
        ("福叶", True),       # Fast speech: "fu ye" (dist=1)
        ("你好", False),      # No match
        ("机器傅里叶", True)  # Embedded
    ]

    print("--- Testing Fuzzy Matching ---")
    all_pass = True
    for text, expected in test_cases:
        pinyin = lazy_pinyin(text)
        match, dist = check_pinyin_match(pinyin, target, threshold=1)

        status = "PASSED" if match == expected else "FAILED"
        if not match == expected:
            all_pass = False

        print(f"Text: '{text}' -> Pinyin: {pinyin}")
        print(f"   Match: {match} (Dist: {dist}) | Expected: {expected} -> {status}")
        print("-" * 30)

    if all_pass:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed.")

if __name__ == "__main__":
    run_test()
