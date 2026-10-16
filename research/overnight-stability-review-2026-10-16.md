# Overnight stability and discovery follow-through — 2026-10-16

Evidence read from actual Actions artifacts before changing source selections.

| Evidence | Published | Normal Primary QA | Local Primary override | Missing | Single observed host |
| --- | ---: | ---: | ---: | ---: | ---: |
| Run 38801238029 / artifact 12004774994 | 89 | 87 | 1 | 22 | 59 |
| Run 38874991740 / artifact 12036107291 (blocked) | 82 | 80 | 1 | 29 | 63 |
| Run 38888392647 / artifact 12041237835 (deployed) | 86 | 85 | 1 | 25 | 60 |

Published count is not a normal QA release count. The 89 build has one additional controlled rescue outside normal health qualification. Different hostnames do not prove independent origin.

## Actual losses

Canonical identity comparison of the 89 and latest 86 outputs loses Bravo.us, DisneyJunior.us and TeenNick.us. NickJr.us remains published, changing from the East suffix to its base ID; this is not a lost or recovered channel.

- Bravo's sole normal origin at 41.205.93.154 returned HTTP 404 in the latest build.
- Disney Junior's AynaScope, 212.5.144.156 and Vercel candidates all timed out. No passing backup remained in that build.
- TeenNick's AynaScope lead timed out; historical alternatives remained failed/cooling down.
- The blocked 82 build shows HTTP 403 for Disney Channel, History and National Geographic on 212.5.144.156. All three returned to normal QA in the latest 86 build.

These are observed access failures, not evidence of a geographic cause. Do not clear cooldowns, force selection, accept stale streams or weaken decoder/continuity gates to improve the count.

## Discoveries and source maintenance

Production scrub 38801238029/artifact 12005632737 found 20 distinct new URLs; latest inventory artifact 12042475259 preserves them. Their labels are leads, not identity verification. Four obvious nonqualifying feeds are excluded from the targeted research batch: Belgian-region Bloomberg, CNN's Pluto FAST feed, New Zealand Outdoor TV, and Reelz's Tubi FAST service. Remaining 16 candidates are queued for normal burn-in/decoder checks in PR123's isolated research workflow. Any passing media still needs programming/schedule review and staging before promotion.

The sole latest playlist error is a deleted date-specific epg-pw_20261015.m3u document. Its project's maintained output/all_merged.m3u is already configured; remove the expired duplicate rather than changing a date every day. Source errors now expose status codes without exception strings, and summaries distinguish unprobed retained leads from decoder-passing but unapproved leads.

PR121 is refreshed against current main for fresh guarded staging. PR123 is refreshed with actual scraper follow-up. Neither old failed head is eligible for merge. Preserve the 86 floor, critical identities, cron `7 */2 * * *`, concurrency, all playback gates, and version 0.7.0. The v0.9.0 scheduled streak remains 0/3.
