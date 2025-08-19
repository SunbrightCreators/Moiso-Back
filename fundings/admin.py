from django.contrib import admin
from .models import Funding, Reward, ProposerReward, ProposerLikeFunding, ProposerScrapFunding, FounderScrapFunding

admin.site.register(Funding)
admin.site.register(Reward)
admin.site.register(FundingImage)
admin.site.register(FundingVideo)
