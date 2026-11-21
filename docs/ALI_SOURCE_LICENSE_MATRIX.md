# Ali Algomori — source and license review matrix

**Review date:** 2026-11-21  
**Purpose:** source discovery and rights-aware ingestion planning. This document is not a legal opinion. A license must be checked for the exact dataset/article/version before ingestion.

## Core policy

1. Open access does not automatically mean open license.
2. Store bibliographic metadata and a stable link even when full-text ingestion is not allowed.
3. The local index accepts only text the operator is authorized to copy and process. The ingest command requires an explicit license basis, reviewer, and review date.
4. `open_license` is reserved for licenses that permit adaptation and redistribution compatible with the intended GEOLOGIA distribution. The ingest validator rejects common non-commercial and no-derivatives Creative Commons terms from this category.
5. Obtain written permission when the license is restrictive or unclear. Otherwise keep metadata and links only.
6. No source full text is downloaded or ingested automatically by the research-sync workflow.

## Reviewed source families

| Country / institution | Source family | Rights status observed | GEOLOGIA handling |
|---|---|---|---|
| United States — USGS | USGS-authored reports and data | USGS says its authored/produced data and information are generally U.S. public domain, with third-party figures/photos and partner datasets excluded or separately restricted. | Eligible only after checking the specific product and third-party components; preserve attribution. |
| United States — USGS | MODFLOW 6.8.0 release | The 2026 release record marks this release CC0 1.0 Universal. | Metadata/reference eligible; software and documentation versions must be pinned. |
| United States — USGS / NASA | Landsat products | USGS identifies USGS Landsat products as public domain and requests source citation. | Dataset/product-specific ingestion is eligible after checking ancillary layers and product citation. |
| United Kingdom — BGS | OpenGeoscience API data | BGS identifies a selection of OpenGeoscience data under the Open Government Licence and provides required acknowledgement. Other BGS products may have separate terms or fees. | Only the specifically identified OGL dataset/API product is eligible; do not generalize the license to all BGS material. |
| Russia — Geophysical Center, Russian Academy of Sciences | Russian Journal of Earth Sciences | Publisher policy page states CC BY 4.0, but the page currently contains unrelated injected-looking text below the policy. | Policy-page integrity is uncertain: metadata/link only until the publisher confirms the current policy and the article license. |
| China — China Geological Survey / China Geology | China Geology journal | Publisher's open-access page states CC BY-NC-ND for articles under its OA policy. | Metadata/link only in GEOLOGIA's public index by default. Do not ingest or redistribute full text under the `open_license` category; seek separate permission if needed. |
| Iraq — University of Mosul | Iraqi National Journal of Earth Science (INJES) | Journal page states CC BY 4.0 for its published material, with license history/version language that should be checked for each article and current issue. | Candidate source for Arabic/English regional geology; verify the article's own license and citation before ingestion. |
| Saudi Arabia — King Abdulaziz University | Scientific Publishing Center journals | Publisher-level policy covers a portfolio; individual journals retain journal-specific policies and article rights. | Do not apply a blanket KAU license. Verify the journal and article page separately. |
| Yemen — Geological Survey and Mineral Resources Board | Maps, bulletins, and reports | Government/institution ownership does not itself prove a reusable license; no exact item-level license has been verified in this audit. | Discovery metadata only until an official item-level rights statement is located. |
| Qatar — Qatar University Earth Sciences / research groups | Theses, datasets, and research outputs | Repository and item licenses vary; no blanket license verified. | Record metadata and check each repository item license before ingestion. |

## Official policy/reference links

- USGS copyright and third-party material: https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted
- USGS data licensing: https://www.usgs.gov/data-management/data-licensing
- MODFLOW 6.8.0 release and CC0 rights: https://www.usgs.gov/software/modflow-version-680
- Landsat public-domain and citation policy: https://www.usgs.gov/faqs/are-landsat-data-cloud-still-considered-be-within-public-domain
- BGS APIs, OpenGeoscience scope, OGL terms, and acknowledgement: https://www.bgs.ac.uk/technologies/web-services/api/
- Russian Journal of Earth Sciences copyright policy: https://rjes.ru/en/nauka/page/copyright
- China Geology OA license terms: https://www.keaipublishing.com/en/journals/china-geology/open-access-journal/
- INJES, University of Mosul license/about page: https://earth.uomosul.edu.iq/index.php/earth/en
- King Abdulaziz University Scientific Publishing Center policies: https://kauj.researchcommons.org/kau-policies.html

## Current ingestion state

The 24-note four-language core pack in `src/geologia/data/knowledge_seed/` is original GEOLOGIA-authored process guidance released under the repository's AGPL-3.0 license. It links to official sources but does not copy their full text.

The international institution catalog and Crossref candidates remain discovery metadata. No USGS/BGS/Russian/Chinese/Arabic journal full text is included in the built-in pack. External documents must be reviewed and explicitly ingested by an operator.
