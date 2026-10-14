# Stride — MVP Product Requirements

## Purpose
Help learners decide what to learn next through focused reading, scenario practice, detailed correction, and targeted revision.

## Intended learners
- Students preparing for exams.
- Candidates preparing for technical interviews.
- People building foundations in a new field.

## Problem
Learners have substantial reading material but struggle to organize it, identify gaps in understanding, and choose useful next steps.

## Shared learning workflow
Choose a goal → upload materials → read a focused guide → answer scenarios → receive correction → practise weak concepts → revisit later.

## Target MVP features
1. Create a learning journey with a goal and optional syllabus or topic outline.
2. Upload supported documents and see processing status.
3. Generate focused guides with source references and a topic coverage map.
4. Choose multiple-choice, typed-answer, or mixed practice.
5. Receive explanations grounded in uploaded materials.
6. Paste code for review during technical practice.
7. Save attempts, identify weak topics, and recommend the next activity.
8. Download focused guides and save progress between sessions.

## Goal-specific behavior
| Goal | Emphasis |
|---|---|
| Exam | Syllabus coverage and exam-style scenarios |
| Technical interview | Relevant concepts, reasoning, pasted code, and mixed problems |
| New field | Prerequisites, foundations, and increasing difficulty |

## Outside MVP scope
- Code execution, an integrated code editor, or guaranteed code correctness.
- Automatic job applications or live opportunity discovery.
- Full offline interactive practice.
- Production-scale infrastructure or support for every language and file type.

## Success criteria
A learner can complete the shared workflow, resume saved progress, trace feedback to sources, and receive a next step based on their attempts. Evaluate usefulness through later unseen questions and learner feedback; do not treat satisfaction alone as evidence of learning.

## Design constraints
Keep interfaces simple and text-focused. Minimize data use, protect private materials and learner records, and account for accessibility. Declare supported languages and formats. Guidance about qualifications or opportunities must come from supplied, identifiable sources.

## Implementation status
Account login, owned journeys, multi-document uploads, automatic plan refresh, saved guides/chat/attempts, weak-topic recommendations, supported versus independent practice, delayed reassessment scheduling, and source comparison/learner decisions are implemented. Plans are provisional; production account recovery, complete syllabus mapping, hint controls, streaming, external fact verification, and live learner validation remain pending.
