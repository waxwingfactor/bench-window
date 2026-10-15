# Research, alternatives, and positioning

Research date: **2026-10-15**. This is a bounded desk-research record, not evidence of interviews, adoption, customer satisfaction, measured savings, or scientific validation. Product descriptions below report public documentation reviewed on that date; they are not hands-on evaluations of commercial installations.

## Decision and confidence

The selected workflow is a short, manually executed bench session with individually declared tasks, shared exclusive resources, dependencies, and timing windows. The user supplies the operational requirements. bench-window finds a schedule within its documented bounds, checks a supplied schedule independently, and can plan around task starts the user has fixed to observed times.

**Opportunity confidence: low to moderate.** Published work establishes that laboratory procedures can have coupled resource and timing constraints. Existing products already solve much of the general scheduling problem. The inferred opportunity is the convenience of an installable, offline tool for a small manual run, including a separate schedule checker and readable run sheet. The research does not establish how many people want this exact workflow, or that it is better than a spreadsheet for every small run. No claim of universal uniqueness is made.

The algorithmic problem is established. A limit of 40 tasks is a supported product boundary, not a discovered market segment or a claim of mathematical novelty. Different syntax or a smaller dependency footprint alone would be weak differentiation; the complete input → feasibility result → run sheet → independent check → updated plan workflow is the relevant comparison.

## Three separate research passes

These were separately directed searches using different source classes, all on 2026-10-15. They are not three customer studies or three human opinions. This record was prepared by an AI discovery agent for the project lead; it is not a human review or customer reference.

### Pass 1: documented operational problem

The [S-LAB paper by Itoh, Horinouchi, and colleagues](https://pmc.ncbi.nlm.nih.gov/articles/PMC8641030/) models laboratory operations with upper bounds between operation boundaries, alongside allocation of instruments. It demonstrates that ordinary precedence alone can be insufficient. Its focus is laboratory automation; applying this problem to a small manual bench run is an inference, not a result established by that study.

The later [SAGAS paper](https://www.sciencedirect.com/science/article/pii/S2472630323000195) explicitly discusses coordinating instruments and human experimenters and evaluates schedules using real experimental protocols. This supports the relevance of combined human/equipment scheduling, while also showing that capable prior methods exist. bench-window does not claim those papers' experimental results, optimization performance, or biological conclusions.

The [StaggR paper, version 3](https://f1000research.com/articles/14-927/v3), documents the practical difficulty of arranging timed parallel bench work. It expressly limits its implementation to identical treatment schedules with a regular staggering interval. It also makes a useful counterargument: irregular machine-optimized schedules can be awkward for humans. An output that is feasible on paper still needs review for practical handling time and clarity.

**Finding:** the broad coordination problem is documented. The exact demand for a JSON-driven, small-run feasibility/checking CLI remains inferred.

### Pass 2: current native and commercial alternatives

| Alternative | Publicly documented capability | Implication for this project |
| --- | --- | --- |
| [LabCollector LSM changelog](https://labcollector.com/lsm-changelog/) | Entries dated 2026-10-12–13 describe operator/equipment timelines, availability and rule constraints, proposed plans, disruption replanning, preview/apply, and checks against changed tests. | This is substantial competition for laboratory planning. Do not claim that LIMS products cannot replan around disruptions. The reviewed page does not establish whether its model matches every supported bench-window constraint. |
| [HighRes Cellario OS and Scheduler](https://www.highres.com/lab-orchestration) | Coordinates manual and automated tasks, parallel workflows, shared resources, dependencies, simulation, and recovery. | A strong option for an organization seeking integrated orchestration. Manual-task support is already available; bench-window's scope is a local planning artifact without instrument integration. |
| [Thermo Fisher's Momentum scheduling description](https://www.thermofisher.com/blog/connectedlab/what-is-a-lab-scheduler-and-why-it-matters/) | Describes timing, sequencing, resource coordination, dynamic response, and integration in automated laboratories. | Timing-aware scheduling is an existing product category. A laboratory needing automation, connected control, or regulated execution should evaluate this category rather than assume this CLI substitutes for it. |
| [Labi](https://getlabi.app/) | Advertises simultaneous protocol runs, independent timers, local records, deviation logging, and export. The page still mixes launch and early-access wording. | A relevant protocol-execution alternative; current availability was not independently installed or verified. A set of parallel timers is not the neglected feature being claimed here. |

**Finding:** enterprise coordination and bench execution have good alternatives. This project is justified only for a user who wants a bounded local planning/checking workflow and does not need those broader systems.

### Pass 3: open-source methods and small bench tools

| Alternative | What was verified in public material | Boundary of the comparison |
| --- | --- | --- |
| [StaggR source and README](https://github.com/amfrancette/StaggR) | Interactive stagger-interval planning, conflict display, chronological schedules, live countdowns, saved sessions, and exports. | Prefer it for identical sample protocols at a regular cadence. Individually specified heterogeneous task graphs are a different supported input model; this is not a claim that the broader scheduling problem is new. |
| [SLab.jl](https://github.com/labauto/SLab.jl) | Official open-source implementation of S-LAB, installed with Julia and its project dependencies; example execution generates a schedule PDF. | A strong existing scheduling implementation. The README demonstrates an automation/research workflow, not a standalone independent checker for a manually edited bench-window schedule. That is a documentation observation, not proof that it cannot be extended. |
| [PythonLab Scheduler on PyPI](https://pypi.org/project/labscheduler/) | Lists cross-job precedences, hard and soft time constraints, machine capacities, Python use, and a SiLA service interface. The visible release was 0.2.43, dated 2025-05-23. | Broad modeling already exists in Python. Its linked documentation could not be retrieved during this pass, so exact support for simultaneous named resources and fixed observed starts was not established. Do not label those features absent. |
| [Lab Laps multi-timer](https://www.lablaps.com/multi-timer) and [Scientific Timer](https://apps.apple.com/tr/app/scientific-timer/id6741395405) | Named concurrent timers; the latter describes protocol steps and timers that continue while the app is closed. | Good tools for managing countdowns. They make a timer-only product insufficiently differentiated. Their reviewed descriptions do not establish a constraint-feasibility or independent schedule-checking workflow. |

**Finding:** there is no basis for claiming no alternatives. The remaining hypothesis is an accessible whole workflow for a small declared model, with explicit unknown/infeasible outcomes and independent checking, rather than a new solver or a replacement for existing orchestration platforms. Missing search results were not treated as evidence that a product does not exist.

## Rejected discovery hypotheses

### Freezer defrost relocation

The pain is documented. [Penn's freezer-maintenance procedure](https://ehrs.upenn.edu/health-safety/biosafety/research-compliance/refrigerator-freezer-inventory-and-maintenance) calls for arranging backup space and moving racks. [Utah's storage guidance](https://ibc.utah.edu/_resources/documents/fact-sheets-and-sops/storing-biohazardous-materials_fact-sheet.pdf) describes difficulty finding temporary freezer capacity. [University of Washington backup-freezer policy](https://biology.washington.edu/facilities/research/backup-freezers) asks for box/rack dimensions and assigns backup locations.

However, [Benchling Inventory documentation](https://help.benchling.com/hc/en-us/articles/39943809066637-Create-and-track-samples-with-the-Inventory) already describes location capacity enforcement, bulk moves, and movement history. [Freezerworks](https://www.freezerworks.com/support-videos/visual-freezers-part-2) has capacity-visible subdivision moves, a staging workbench, pending moves, and history. [OpenSpecimen container actions](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/2558525545/Container+Actions) includes check-out with reserved home positions and check-in to those positions. The candidate was rejected because generic relocation/custody was served and its proposed ordered-move workflow also overlapped a higher-priority product claim in this batch.

### Core usage versus reservation reconciliation

[Northeastern's imaging-core guidelines](https://cils.northeastern.edu/forms-guidelines/) describe staff checking actual start/end records and adjusting reservations. This is real administrative work. But [iLab Confirm Usage](https://help.ilab.agilent.com/37446-managing-schedule-equipment/266094-confirm-usage) already supports matching uploaded actual usage against scheduled usage, while its [Kiosk](https://help.ilab.agilent.com/42925-kiosk-and-interlock/297897-managing-kiosk) compares logged and scheduled time. [Calpendo](https://calpendo.com/calpendo-features) and [Stratocore PPMS](https://www.stratocore.com/features) also document actual-usage tracking. Generic reconciliation was therefore rejected. A hypothetical clock-diagnostics feature did not, by itself, establish a sufficiently distinct demand.

## Applying Crossing the Chasm selectively

Moore's own [Crossing the Chasm description](https://geoffreyamoore.com/book/crossing-the-chasm/) emphasizes a specific use case and a complete solution that pragmatic users can assess. His [positioning guidance](https://geoffreyamoore.com/positioning/) highlights a narrow beachhead, the whole product, and clear differentiation. The [Chasm Group's discussion of adoption mistakes](https://chasmgroup.com/7-deadly-sins-how-to-successfully-cross-the-chasm-with-cloud-based-solutions-by-avoiding-these-mistakes/) distinguishes a customer's reason to adopt from a seller's enthusiasm and recommends simplifying the complete adoption path.

These ideas guide scope and usability here. This open-source release does not claim to have crossed a market chasm. No reference customers, revenue model, distribution partnership, or financial strategy is invented.

- **Beachhead hypothesis:** a research technician or scientific programmer who already maintains explicit timing requirements for one short heterogeneous bench run, can review JSON, and needs both operator and equipment conflicts checked before carrying out the plan.
- **Compelling reason to use:** a declared maximum lag or shared-resource conflict can make a hand-arranged run sheet impossible; after a delayed start, simply shifting every later task may violate another window. This is a constructed operational rationale, not a measured frequency or saving.
- **Market alternative:** a hand-maintained spreadsheet, Gantt chart, or paper run sheet, combined with manual review and separate timers. For simple runs this may remain the better choice.
- **Product alternative:** StaggR for regular identical runs; SLab.jl or PythonLab Scheduler for a broader programmable model; integrated commercial systems when orchestration and institutional operation matter.
- **Whole product within scope:** an installable offline CLI, strict documented input contracts, editable examples, a bounded feasibility planner, a readable run sheet, an independently implemented schedule checker, meaningful acceptance tests, and clear failure/limit documentation. The release and verification records establish which of these were actually shipped.

### Original two-sentence positioning

For research technicians who already encode short heterogeneous bench runs and need to know whether declared timing windows fit around one operator and shared equipment, bench-window is an offline run-planning CLI that produces and checks schedules from explicit constraints. Unlike fixed-cadence tools such as StaggR, it accepts individually declared dependencies and fixed observed starts, and supplies validation, editable examples, readable run sheets, documented limits, and installable distributions for completing that small workflow.

### Constructed usage scenario

This example is fictional and is not a biological protocol or customer account. One technician has two different preparation workstreams and a shared reader; some tasks need the technician alone, some also need equipment, and some wait periods release the technician. The technician enters durations and lag bounds taken from their approved local procedures, inspects a feasible run sheet, records a task that started seven minutes later than planned, and requests another feasible arrangement with that start fixed. The checker can also reject a manually edited schedule that double-books the reader or violates a declared time bound. The tool cannot tell whether the entered requirements are scientifically or operationally adequate.

## Evidence limits and next useful validation

This record supports the existence of the scheduling problem and the strength of alternatives. It leaves the exact beachhead's adoption need unvalidated. Useful future evidence would be consented testing with technicians comparing realistic heterogeneous run sheets against their current workflow, including whether JSON entry and irregular start times impose more burden than they remove. No such study was conducted for this release.

Software tests and published-artifact checks establish software behavior only. They do not validate a laboratory procedure, replace local review, certify safe handling, prove regulatory compliance, or establish commercial demand.
