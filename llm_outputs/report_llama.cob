      *> ============================================================
      *> REPORT_GENERATOR.COB — Llama "Fix" Output
      *> SYNTHETIC EXAMPLE
      *>
      *> LLAMA BEHAVIOR:
      *>   FIXED:   Nothing (Llama did not detect any bugs)
      *>   MISSED:  All 4 bugs from benchmark remain
      *>   NEW BUG: Added REDEFINES on WS-SECTION-TOTAL (numeric)
      *>            Packed decimal bytes reinterpreted as alphanumeric
      *>   NEW BUG: COMPUTE without ON SIZE ERROR added for totals
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPORT-GENERATOR.
       AUTHOR. LLAMA-FIX-V1.
       DATE-WRITTEN. 2024-01-15.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT GL-INPUT-FILE
               ASSIGN TO 'GLTRANS.DAT'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT REPORT-FILE
               ASSIGN TO 'GLRPT.OUT'
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.

       FD GL-INPUT-FILE.
       01  GL-RECORD.
           05  GL-ACCOUNT-CODE     PIC X(10).
           05  GL-SECTION          PIC X(4).
           05  GL-DESCRIPTION      PIC X(40).
           05  GL-DEBIT-AMOUNT     PIC 9(9)V99.
           05  GL-CREDIT-AMOUNT    PIC 9(9)V99.
           05  GL-POSTING-DATE     PIC 9(8).

       FD REPORT-FILE.
       01  REPORT-RECORD           PIC X(132).

       WORKING-STORAGE SECTION.

       01  WS-CONTROL-FIELDS.
           05  WS-EOF-FLAG         PIC X VALUE 'N'.
               88  END-OF-FILE     VALUE 'Y'.
           05  WS-PREV-SECTION     PIC X(4) VALUE SPACES.
           05  WS-LINE-COUNT       PIC 9(4) VALUE 0.
           05  WS-PAGE-COUNT       PIC 9(3) VALUE 1.
           05  WS-PAGE-LIMIT       PIC 9(4) VALUE 60.

       01  WS-ACCUMULATORS.
           05  WS-SECTION-TOTAL    PIC 9(11)V99 VALUE ZEROS.
      *>   LLAMA NEW BUG: REDEFINES on numeric field.
      *>   PIC X(7) reinterprets the packed decimal total bytes.
      *>   Arithmetic on WS-SECTION-TOTAL after REDEFINES use
      *>   produces corrupt values.
           05  WS-SECTION-TOTAL-X  REDEFINES WS-SECTION-TOTAL
                                   PIC X(7).
           05  WS-GRAND-TOTAL      PIC 9(13)V99 VALUE ZEROS.
           05  WS-NET-AMOUNT       PIC S9(9)V99.

       01  WS-REPORT-HEADER.
           05  FILLER              PIC X(40)
               VALUE 'MONTHLY GENERAL LEDGER SUMMARY REPORT'.
           05  FILLER              PIC X(20) VALUE SPACES.
           05  WS-RPT-DATE         PIC X(10).

       01  WS-DETAIL-LINE.
           05  DET-ACCOUNT         PIC X(10).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  DET-DESCRIPTION     PIC X(40).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  DET-DEBIT           PIC $$$,$$$,$$9.99.
           05  FILLER              PIC X(2) VALUE SPACES.
           05  DET-CREDIT          PIC $$$,$$$,$$9.99.

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-INITIALIZE
           PERFORM 2000-PROCESS-GL
               UNTIL END-OF-FILE
           PERFORM 3000-WRITE-TOTALS
           PERFORM 4000-FINALIZE
           STOP RUN.

       1000-INITIALIZE.
      *>   LLAMA MISSED: OPEN with no FILE STATUS check unchanged.
           OPEN INPUT GL-INPUT-FILE
           OPEN OUTPUT REPORT-FILE
           PERFORM 1100-WRITE-PAGE-HEADER
           READ GL-INPUT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       1100-WRITE-PAGE-HEADER.
           MOVE SPACES TO REPORT-RECORD
           MOVE WS-REPORT-HEADER TO REPORT-RECORD
      *>   LLAMA MISSED: WRITE to potentially-unopened file unchanged.
           WRITE REPORT-RECORD.

       2000-PROCESS-GL.
           IF GL-SECTION NOT = WS-PREV-SECTION
               IF WS-PREV-SECTION NOT = SPACES
                   PERFORM 2500-WRITE-SECTION-TOTAL
               END-IF
               MOVE GL-SECTION TO WS-PREV-SECTION
               MOVE ZEROS TO WS-SECTION-TOTAL
           END-IF
           COMPUTE WS-NET-AMOUNT =
               GL-DEBIT-AMOUNT - GL-CREDIT-AMOUNT
      *>   LLAMA MISSED: COMPUTE without ON SIZE ERROR unchanged.
           COMPUTE WS-SECTION-TOTAL =
               WS-SECTION-TOTAL + GL-DEBIT-AMOUNT
           PERFORM 2100-WRITE-DETAIL-LINE
           READ GL-INPUT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2100-WRITE-DETAIL-LINE.
           MOVE GL-ACCOUNT-CODE  TO DET-ACCOUNT
           MOVE GL-DESCRIPTION   TO DET-DESCRIPTION
           MOVE GL-DEBIT-AMOUNT  TO DET-DEBIT
           MOVE GL-CREDIT-AMOUNT TO DET-CREDIT
           MOVE WS-DETAIL-LINE   TO REPORT-RECORD
           WRITE REPORT-RECORD
           ADD 1 TO WS-LINE-COUNT.

       2500-WRITE-SECTION-TOTAL.
           MOVE SPACES TO REPORT-RECORD
           STRING 'SECTION ' WS-PREV-SECTION ' TOTAL: '
               WS-SECTION-TOTAL
               DELIMITED BY SIZE
               INTO REPORT-RECORD
           WRITE REPORT-RECORD
           ADD WS-SECTION-TOTAL TO WS-GRAND-TOTAL.

       3000-WRITE-TOTALS.
           PERFORM 2500-WRITE-SECTION-TOTAL
           MOVE SPACES TO REPORT-RECORD
           STRING 'GRAND TOTAL: ' WS-GRAND-TOTAL
               DELIMITED BY SIZE
               INTO REPORT-RECORD
           WRITE REPORT-RECORD.

       4000-FINALIZE.
           CLOSE GL-INPUT-FILE
           CLOSE REPORT-FILE.

       END PROGRAM REPORT-GENERATOR.
