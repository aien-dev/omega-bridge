def expanded_image_token_len(n_llm_h, n_llm_w):
    return n_llm_h * (n_llm_w + 1) + 2
