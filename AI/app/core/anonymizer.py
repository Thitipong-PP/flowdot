import re

def mask_pii(text: str) -> str:
    """
    Masks Personally Identifiable Information (PII) for Thai financial context:
    - Thai National ID cards (13 digits, hyphenated or continuous): [ID_CARD_MASKED]
    - Bank Account numbers (10-12 digits, hyphenated or continuous): [BANK_ACC_MASKED]
    - Mobile phone numbers (10 digits starting with 06, 08, 09): [PHONE_MASKED]
    """
    if not text:
        return ""

    # Thai National ID format: 1-1002-00345-67-8 or 13 digits continuous
    text = re.sub(r'\b\d{1}-?\d{4}-?\d{5}-?\d{2}-?\d{1}\b', '[ID_CARD_MASKED]', text)
    text = re.sub(r'\b\d{13}\b', '[ID_CARD_MASKED]', text)

    # Bank Account numbers: 098-2-34567-1, 123-4-56789-0, or 10-12 digits
    text = re.sub(r'\b\d{3}-?\d{1}-?\d{5}-?\d{1,2}\b', '[BANK_ACC_MASKED]', text)
    text = re.sub(r'\b\d{10,12}\b', '[BANK_ACC_MASKED]', text)

    # Phone numbers: 08x-xxx-xxxx, 09x-xxx-xxxx, 06x-xxx-xxxx, or 10 digits
    text = re.sub(r'\b0[689]\d{1}-?\d{3}-?\d{4}\b', '[PHONE_MASKED]', text)

    return text
