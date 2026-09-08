# GitHub comparison and adopted design choices

Reviewed 2026-09-08.

| Project | Useful pattern | Our adoption |
| --- | --- | --- |
| [econ-research-workflow](https://github.com/tsdfs930514/econ-research-workflow) | full lifecycle, adversarial QA, exploration sandbox, cross-engine checks | bounded stage gates, independent audit perspectives, exploratory promotion |
| [EconAgentSkills](https://github.com/JonasWeinert/EconAgentSkills) | method-specific decision trees, human-in-the-loop policy, DIME discipline | explicit identification gates and capability honesty |
| [academic-paper-writer](https://github.com/JonasWeinert/EconAgentSkills/blob/main/_skills/writing/academic-paper-writer/SKILL.md) | identification-first prose, generated numbers, referee-response discipline | manuscript section contracts and numerical claim registry |
| [seele-scholar-agent](https://github.com/onekyuu/seele-scholar-agent) | outline approval, claim-evidence binding, bounded revision, consistency gates | approved outline, claim firewalls and capped audit cycles |
| [literature-review-toolkit](https://github.com/gallantlab/literature-review-toolkit) | antecedent search, canonical bibliography, priority audit | backward citation search and canonical verified references |
| [econ-writing-skill](https://github.com/hanlulong/econ-writing-skill) | paper-type writing, journal conversion, submission and referee responses | distinct paper types and submission-mode references |
| [project_template](https://github.com/rhstanton/project_template) | build provenance and separation of analysis from publication | hashed bundles and an explicit publish gate |
| [PaperAgent](https://github.com/bingdongni/PaperAgent) | lifecycle orchestration with specialized roles | one coordinator over specialist skills, without claiming unnecessary agent consensus |

We do not copy project prompts or vendor dependencies. We adopt the verifiable architectural ideas that address demonstrated gaps in this repository.
