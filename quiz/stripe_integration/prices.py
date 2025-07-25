# quiz/stripe_integration/prices.py

STRIPE_PRICE_IDS = {
    "basic": {
        "1": "price_1RkLfnGb17a8LOzTPGy2XaGQ",
        "3": "price_1RkLi6Gb17a8LOzTnk7lXlxq",
        "6": "price_1RkLioGb17a8LOzTOiILxrzY",
        "12": "price_1RkLjPGb17a8LOzTal2EdaXF",
        # Uncomment the next line to use the Basic plan for testing in test mode
        # "12": "price_1Ro77VGb17a8LOzTO6j3Te2c",
    },
    "pro": {
        # Uncomment the next line to use the Pro plan of $49
        "1": "price_1RkLjoGb17a8LOzTVkryXYZd",
        # Uncomment the next line to use the Pro plan for testing on live
        # "1": "price_1RlxaUGb17a8LOzTQyhxORgb",
        # Uncomment the next line to use the Pro plan in test mode
        # "1": "price_1RkUWjGb17a8LOzTZITqbxrU",
        "3": "price_1RkLkEGb17a8LOzTp852tcXQ",
        "6": "price_1RkLkcGb17a8LOzTFALlCndd",
        "12": "price_1RkLlNGb17a8LOzTHXaQVhTg",
    },
    "enterprise": {
        "1": "price_1RkLlgGb17a8LOzTUhTvVarE",
        "3": "price_1RkLm6Gb17a8LOzTfZfKxXpL",
        # Uncomment the next line to use the Enterprise plan in test mode
        # "3": "price_1Ro76uGb17a8LOzTSECpf00R",
        "6": "price_1RkLmaGb17a8LOzTC18TsDox",
        "12": "price_1RkLn2Gb17a8LOzTOZ49y2AS",
    },
    # uncomment the next line to use the platform fee of $25
    "platform_fee": "price_1RkLnUGb17a8LOzT4KK9PUAb"
    # Uncomment the next line to use the platform fee for testing on live
    # "platform_fee": "price_1RlxjpGb17a8LOzTpBrgW9lg"
    # uncomment the next line to use the platform fee for testing on test mode
    # "platform_fee": "price_1RkUg3Gb17a8LOzTk2vUf13u"
}
