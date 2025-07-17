# quiz/stripe_integration/prices.py

STRIPE_PRICE_IDS = {
    "basic": {
        "1": "price_1RkLfnGb17a8LOzTPGy2XaGQ",
        "3": "price_1RkLi6Gb17a8LOzTnk7lXlxq",
        "6": "price_1RkLioGb17a8LOzTOiILxrzY",
        "12": "price_1RkLjPGb17a8LOzTal2EdaXF",
    },
    "pro": {
        # Uncomment the next line to use the Pro plan of $49
        # "1": "price_1RkLjoGb17a8LOzTVkryXYZd",
        "1": "price_1RlxaUGb17a8LOzTQyhxORgb",
        "3": "price_1RkLkEGb17a8LOzTp852tcXQ",
        "6": "price_1RkLkcGb17a8LOzTFALlCndd",
        "12": "price_1RkLlNGb17a8LOzTHXaQVhTg",
    },
    "enterprise": {
        "1": "price_1RkLlgGb17a8LOzTUhTvVarE",
        "3": "price_1RkLm6Gb17a8LOzTfZfKxXpL",
        "6": "price_1RkLmaGb17a8LOzTC18TsDox",
        "12": "price_1RkLn2Gb17a8LOzTOZ49y2AS",
    },
    # uncomment the next line to use the platform fee of $25
    # "platform_fee": "price_1RkLnUGb17a8LOzT4KK9PUAb"
    "platform_fee": "price_1RlxjpGb17a8LOzTpBrgW9lg"
}
