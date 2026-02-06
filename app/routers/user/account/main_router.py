from aiogram import Router

from .personal_cabinet import router as personal_cabinet_router
from .adult_registration import router as adult_registration_router
from .token_registration import router as token_registration_router
from .child_registration import router as child_registration_router
from .redaction_userdata import router as user_redaction_router
from .redaction_childdata import router as child_redaction_router


router = Router(name="account_main")

# Включаем все подроутеры
router.include_router(personal_cabinet_router)
router.include_router(adult_registration_router)
router.include_router(token_registration_router)
router.include_router(child_registration_router)
router.include_router(user_redaction_router)
router.include_router(child_redaction_router)