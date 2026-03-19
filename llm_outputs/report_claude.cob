      *> ============================================================
      *> REPORT_GENERATOR.COB — Claude "Fix" Output
      *> SYNTHETIC EXAMPLE
      *>
      *> CLAUDE BEHAVIOR:
      *>   FIXED:   Added FILE STATUS on both GL-INPUT and REPORT-FILE
      *>   MISSED:  ON SIZE ERROR on section total COMPUTE absent
      *>   MISSED:  OPEN result not checked in procedure division logic
      *>   NEW BUG: Added WS-PCT-FIELD PIC V99 for percentage calc
      *>            (pure decimal, no integer — PIC_V_NO_INTEGER)
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPORT-GENERATOR.
       AUTHOR. CLAUDE-FIX-V1.
       DATE-WRITTEN. 2024-01-15.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT GL-INPUT-FILE
               ASSIGN TO 'GLTRANS.DAT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-GL-STATUS.
           SELECT REPORT-FILE
               ASSIGN TO 'GLRPT.OUT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-RPT-STATUS.

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
           05  WS-GL-STATUS        PIC XX.
               88  GL-OK           VALUE '00'.
           05  WS-RPT-STATUS       PIC XX.
               88  RPT-OK          VALUE '00'.
           05  WS-EOF-FLAG         PIC X VALUE 'N'.
               88  END-OF-FILE     VALUE 'Y'.
           05  WS-PREV-SECTION     PIC X(4) VALUE SPACES.
           05  WS-LINE-COUNT       PIC 9(4) VALUE 0.
           05  WS-PAGE-LIMIT       PIC 9(4) VALUE 60.

       01  WS-ACCUMULATORS.
      *>   CLAUDE MISSED: No ON SIZE ERROR on COMPUTE using this.
           05  WS-SECTION-TOTAL    PIC 9(11)V99 VALUE ZEROS.
           05  WS-GRAND-TOTAL      PIC 9(13)V99 VALUE ZEROS.
           05  WS-NET-AMOUNT       PIC S9(9)V99.
      *>   CLAUDE NEW BUG: PIC V99 — pure decimal, no integer.
      *>   Percentage values like 0.35 store fine, but values >= 1.0
      *>   (any section > 100% of budget) silently truncate to 0.xx.
           05  WS-PCT-FIELD        PIC V99.

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
           OPEN INPUT GL-INPUT-FILE
           OPEN OUTPUT REPORT-FILE
           PERFORM 1100-WRITE-PAGE-HEADER
           READ GL-INPUT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       1100-WRITE-PAGE-HEADER.
           MOVE SPACES TO REPORT-RECORD
           MOVE WS-REPORT-HEADER TO REPORT-RECORD
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
      *>   CLAUDE MISSED: COMPUTE without ON SIZE ERROR.
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
