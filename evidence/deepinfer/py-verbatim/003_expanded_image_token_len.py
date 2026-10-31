def expanded_image_token_len(n_llm_h: int, n_llm_w: int) -> int:
    """图像段展开后的 token 数：IMAGE_START + 每行（n_llm_w 个 IMAGE + 1 个 NEW_LINE）+ IMAGE_END。"""
    return n_llm_h * (n_llm_w + 1) + 2
