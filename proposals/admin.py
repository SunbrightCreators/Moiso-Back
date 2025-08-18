from django.contrib import admin
from .models import Proposal, ProposerLikeProposal, ProposerScrapProposal, FounderScrapProposal

admin.site.register(Proposal)
admin.site.register(ProposerLikeProposal)
admin.site.register(ProposerScrapProposal)
admin.site.register(FounderScrapProposal)
