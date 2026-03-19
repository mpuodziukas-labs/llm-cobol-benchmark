      *> ============================================================
      *> DATA_VALIDATION.COB — GPT-4 "Fix" Output
      *> SYNTHETIC EXAMPLE
      *>
      *> GPT-4 BEHAVIOR:
      *>   FIXED:   Added FILE STATUS on INPUT-FILE and OUTPUT-FILE
      *>   MISSED:  WHEN OTHER CONTINUE unchanged (added comment only)
      *>   MISSED:  ON SIZE ERROR on annual salary COMPUTE absent
      *>   MISSED:  REDEFINES WS-EMP-ID-X (COMP-3 corruption) unchanged
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATA-VALIDATION.
       AUTHOR. GPT4-FIX-V1.
       DATE-WRITTEN. 2024-01-15.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE
               ASSIGN TO 'HRINPUT.DAT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-IN-STATUS.
           SELECT OUTPUT-FILE
               ASSIGN TO 'HROUT.DAT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OUT-STATUS.
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
           05  WS-IN-STATUS        PIC XX.
               88  IN-OK           VALUE '00'.
           05  WS-OUT-STATUS       PIC XX.
               88  OUT-OK          VALUE '00'.
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
      *>   GPT-4 MISSED: REDEFINES on COMP-3 still present.
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
      *>   GPT-4 MISSED: No ON SIZE ERROR on salary COMPUTE.
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
      *>         GPT-4 MISSED: WHEN OTHER CONTINUE unchanged.
      *>         GPT-4 added "TODO: map to UNKNOWN dept" comment.
               WHEN OTHER
                   CONTINUE *> TODO: map to UNKNOWN department
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
