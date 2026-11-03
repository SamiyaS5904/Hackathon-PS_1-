# Sample Institute of Technology: the quickest way to try Timetabl.ai

One department, one Excel file, about 3 minutes from sign-up to a published timetable. Fictional college and names.
Tested end to end: the upload has 0 errors, and Generate gives **47 classes, 0 clashes, quality 89** in about
35 s, even on a small server.

**Inside `Sample_CSE.xlsx`:** CSE, 3 sections (CSE-1A, CSE-2A, CSE-3A, 60 students each, lab batches A1 / A2),
10 teachers, 12 subjects, 24 classes (lectures + labs), 5 rooms (LH-1 to LH-3, Computer Lab-1 and -2), 180 students.

## Steps

1. **Sign up** (*Get started free*): any college name, your email and a password.
2. **Setup**:
   - *Week & labs*: Mon to Fri, lab length **2 periods**.
   - *Timings*: **1 shift** named **Day**, **8 periods of 60 minutes** from **09:00** (09:00 to 17:00), no fixed
     breaks, mess window **12:00 to 14:00**.
   - *Calendar*: optional.
   - *Departments*: short name **CSE**, name Computer Science and Engineering.
3. **Departments → CSE → Upload filled sheet** → `Sample_CSE.xlsx` → check (0 errors) → **Save**.
4. **Mark Ready**.
5. **Generate** → **0 clashes** → **Publish**.
6. Optional: *More → People & invites* → invite a teacher (e.g. `teacher@sample.test`, role Teacher, CSE).

Student logins: `<roll no>@sample.test`, first password = roll number (e.g. `2601001@sample.test` / `2601001`).
Regenerate the file with `python -m app.seed.sample` in `backend/`.
