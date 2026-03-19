      *> ============================================================
      *> DATA_VALIDATION.COB
      *> HR System — Employee Record Validation and Enrichment
      *> PURPOSE: Read input records, validate required fields,
      *>          enrich with department codes, skip bad records.
      *>
      *> INTENTIONAL BUG PATTERN (common LLM failure):
      *>   BUG #1 — WHEN OTHER CONTINUE in EVALUATE block.
      *>            Unknown DEPT-CODE passes validation silently.
      *>            WS-DEPT-FULL-NAME retains value from previous
      *>            record. Bad records written with wrong department.
      *>   BUG #2 — No FILE STATUS on INPUT-FILE or OUTPUT-FILE.
      *>   BUG #3 — COMPUTE WS-ANNUAL-SALARY without ON SIZE ERROR.
      *>            PIC 9(7)V99 overflows for executive salaries.
      *>   BUG #4 — REDEFINES WS-EMP-ID (numeric) as alphanumeric.
      *>            COMP-3 byte layout corrupted on packed decimal.
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATA-VALIDATION.
       AUTHOR. HR-SYSTEMS-GROUP.
       DATE-WRITTEN. 1997-02-14.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE
               ASSIGN TO 'HRINPUT.DAT'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUTPUT-FILE
               ASSIGN TO 'HROUT.DAT'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT ERROR-FILE
               ASSIGN TO 'HRERROR.DAT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-ERR-STATUS.

       DATA DIVISION.
       FILE SECTION.

       FD INPUT-FILE.
       01  INPUT-RECORD.
           05  IN-EMP-ID           PIC 9(6).
           05  IN-EMP-NAME         PIC X(30).
           05  IN-DEPT-CODE        PIC X(3).
           05  IN-JOB-GRADE        PIC 9(2).
           05  IN-MONTHLY-SALARY   PIC 9(5)V99.
           05  IN-HIRE-DATE        PIC 9(8).
           05  IN-STATUS           PIC X(1).
               88  ACTIVE          VALUE 'A'.
               88  INACTIVE        VALUE 'I'.
               88  TERMINATED      VALUE 'T'.

       FD OUTPUT-FILE.
       01  OUTPUT-RECORD           PIC X(132).

       FD ERROR-FILE.
       01  ERROR-RECORD            PIC X(132).

       WORKING-STORAGE SECTION.

       01  WS-STATUS-FLAGS.
           05  WS-ERR-STATUS       PIC XX.
               88  ERR-SUCCESS     VALUE '00'.
           05  WS-EOF-FLAG         PIC X VALUE 'N'.
               88  END-OF-FILE     VALUE 'Y'.
           05  WS-VALID-FLAG       PIC X VALUE 'Y'.
               88  RECORD-VALID    VALUE 'Y'.
           05  WS-RECORD-COUNT     PIC 9(6) VALUE 0.
           05  WS-ERROR-COUNT      PIC 9(4) VALUE 0.

       01  WS-ENRICHMENT.
           05  WS-DEPT-FULL-NAME   PIC X(30).
           05  WS-ANNUAL-SALARY    PIC 9(7)V99.
           05  WS-GRADE-DESC       PIC X(20).

       01  WS-WORK-FIELDS.
      *>   BUG #4: REDEFINES on numeric (COMP-3) field.
      *>   WS-EMP-ID used for internal processing as packed decimal.
      *>   Redefining as PIC X(3) corrupts COMP-3 byte interpretation.
           05  WS-EMP-ID           PIC 9(6) COMP-3.
           05  WS-EMP-ID-X         REDEFINES WS-EMP-ID PIC X(3).

       01  WS-OUTPUT-LINE.
           05  OUT-EMP-ID          PIC 9(6).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  OUT-EMP-NAME        PIC X(30).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  OUT-DEPT-FULL       PIC X(30).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  OUT-ANNUAL-SALARY   PIC $$$,$$$,$$9.99.

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-OPEN-FILES
           PERFORM 2000-PROCESS-RECORDS
               UNTIL END-OF-FILE
           PERFORM 3000-CLOSE-FILES
           STOP RUN.

       1000-OPEN-FILES.
           OPEN INPUT INPUT-FILE
           OPEN OUTPUT OUTPUT-FILE
           OPEN OUTPUT ERROR-FILE
           READ INPUT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2000-PROCESS-RECORDS.
           MOVE 'Y' TO WS-VALID-FLAG
           PERFORM 2100-VALIDATE-RECORD
           IF RECORD-VALID
               PERFORM 2200-ENRICH-RECORD
               PERFORM 9000-WRITE-OUTPUT
           ELSE
               PERFORM 9100-WRITE-ERROR
           END-IF
           ADD 1 TO WS-RECORD-COUNT
           READ INPUT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2100-VALIDATE-RECORD.
           IF IN-EMP-ID = ZEROS
               MOVE 'N' TO WS-VALID-FLAG
           END-IF
           IF IN-EMP-NAME = SPACES
               MOVE 'N' TO WS-VALID-FLAG
           END-IF
           IF IN-MONTHLY-SALARY = ZEROS
               MOVE 'N' TO WS-VALID-FLAG
           END-IF.

       2200-ENRICH-RECORD.
      *>   BUG #3: No ON SIZE ERROR on annual salary compute.
      *>   Executive with $85,000/month = $1,020,000/yr overflows
      *>   PIC 9(7)V99 = max $9,999,999.99. Silent truncation.
           COMPUTE WS-ANNUAL-SALARY =
               IN-MONTHLY-SALARY * 12
           EVALUATE IN-DEPT-CODE
               WHEN 'ENG'
                   MOVE 'ENGINEERING' TO WS-DEPT-FULL-NAME
               WHEN 'FIN'
                   MOVE 'FINANCE' TO WS-DEPT-FULL-NAME
               WHEN 'HRL'
                   MOVE 'HUMAN RESOURCES' TO WS-DEPT-FULL-NAME
               WHEN 'OPS'
                   MOVE 'OPERATIONS' TO WS-DEPT-FULL-NAME
               WHEN 'MKT'
                   MOVE 'MARKETING' TO WS-DEPT-FULL-NAME
      *>         BUG #1: WHEN OTHER CONTINUE.
      *>         Unknown DEPT-CODE passes through without clearing
      *>         WS-DEPT-FULL-NAME. Previous record's department
      *>         is written for the current invalid record.
      *>         LLMs see this and leave CONTINUE with a comment.
               WHEN OTHER
                   CONTINUE
           END-EVALUATE.

       9000-WRITE-OUTPUT.
           MOVE IN-EMP-ID        TO OUT-EMP-ID
           MOVE IN-EMP-NAME      TO OUT-EMP-NAME
           MOVE WS-DEPT-FULL-NAME TO OUT-DEPT-FULL
           MOVE WS-ANNUAL-SALARY TO OUT-ANNUAL-SALARY
           MOVE WS-OUTPUT-LINE   TO OUTPUT-RECORD
           WRITE OUTPUT-RECORD.

       9100-WRITE-ERROR.
           ADD 1 TO WS-ERROR-COUNT
           MOVE INPUT-RECORD TO ERROR-RECORD
           WRITE ERROR-RECORD.

       3000-CLOSE-FILES.
           CLOSE INPUT-FILE
           CLOSE OUTPUT-FILE
           CLOSE ERROR-FILE.

       END PROGRAM DATA-VALIDATION.
