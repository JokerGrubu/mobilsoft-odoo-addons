{
    "name": "Joker Grubu AI Theme",
    "description": "Joker Grubu kurumsal web sitesi için koyu AI temalı özelleştirme modülü.",
    "category": "Theme",
    "version": "19.0.1.0.0",
    "depends": ["website", "theme_graphene"],
    "data": [
        "data/ir_asset.xml",
        "views/homepage.xml"
    ],
    "assets": {
        "web._assets_primary_variables": [
            "theme_joker_grubu/static/src/scss/primary_variables.scss"
        ],
        "web.assets_frontend": [
            "theme_joker_grubu/static/src/scss/custom.scss"
        ]
    },
    "author": "Joker Grubu",
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
}
