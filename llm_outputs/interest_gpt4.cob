      *> ============================================================
      *> INTEREST_CALCULATION.COB — GPT-4 "Fix" Output
      *> SYNTHETIC EXAMPLE
      *>
      *> GPT-4 BEHAVIOR:
      *>   FIXED:   PIC V9(6) → PIC 9V9(6) for WS-RATE-DAILY
      *>   MISSED:  ON SIZE ERROR on compound interest COMPUTE absent
      *>   MISSED:  FILE STATUS on ACCOUNT-FILE absent
      *>   MISSED:  WHEN OTHER CONTINUE still present
      *>   NEW BUG: Introduced WS-TEMP-RATE PIC V9(4) (regression)
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTEREST-CALC.
       AUTHOR. GPT4-FIX-V1.
       DATE-WRITTEN. 2024-01-15.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCOUNT-FILE
               ASSIGN TO 'ACCOUNTS.DAT'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT INTEREST-OUTPUT
               ASSIGN TO 'INTEREST.OUT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OUT-STATUS.

       DATA DIVISION.
       FILE SECTION.

       FD ACCOUNT-FILE.
       01  ACCOUNT-RECORD.
           05  ACCT-NUMBER         PIC 9(10).
           05  ACCT-BALANCE        PIC 9(9)V99.
           05  ACCT-ANNUAL-RATE    PIC 9(1)V9(4).
           05  ACCT-DAYS           PIC 9(4).
           05  ACCT-TYPE           PIC X(2).
               88  SAVINGS         VALUE 'SV'.
               88  CHECKING        VALUE 'CK'.
               88  MONEY-MARKET    VALUE 'MM'.

       FD INTEREST-OUTPUT.
       01  INTEREST-LINE           PIC X(80).

       WORKING-STORAGE SECTION.

       01  WS-STATUS-FLAGS.
           05  WS-OUT-STATUS       PIC XX.
               88  OUT-SUCCESS     VALUE '00'.
           05  WS-EOF-FLAG         PIC X VALUE 'N'.
               88  END-OF-FILE     VALUE 'Y'.

       01  WS-CALC-FIELDS.
      *>   GPT-4 FIX: PIC V9(6) → PIC 9V9(6). Correct.
           05  WS-RATE-DAILY       PIC 9V9(6).
           05  WS-INTEREST-AMOUNT  PIC 9(9)V4.
           05  WS-FINAL-BALANCE    PIC 9(9)V99.
           05  WS-PERIOD-FACTOR    PIC 9(3)V9(6).
           05  WS-COMPOUND-FACTOR  PIC 9(3)V9(8).
      *>   GPT-4 NEW BUG: PIC V9(4) introduced for intermediate calc.
      *>   Any value >= 1.0 silently truncates. Reg Z violation path.
           05  WS-TEMP-RATE        PIC V9(4).

       01  WS-OUTPUT-LINE.
           05  OUT-ACCT-NUMBER     PIC 9(10).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  OUT-INTEREST        PIC $$$,$$$,$$9.9999.
           05  FILLER              PIC X(2) VALUE SPACES.
           05  OUT-NEW-BALANCE     PIC $$$,$$$,$$9.99.

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-OPEN-FILES
           PERFORM 2000-PROCESS-ACCOUNTS
               UNTIL END-OF-FILE
           PERFORM 3000-CLOSE-FILES
           STOP RUN.

       1000-OPEN-FILES.
           OPEN INPUT ACCOUNT-FILE
           OPEN OUTPUT INTEREST-OUTPUT
           READ ACCOUNT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2000-PROCESS-ACCOUNTS.
           EVALUATE TRUE
               WHEN SAVINGS
                   PERFORM 2100-CALC-COMPOUND
               WHEN CHECKING
                   PERFORM 2200-CALC-SIMPLE
               WHEN MONEY-MARKET
                   PERFORM 2100-CALC-COMPOUND
               WHEN OTHER
                   CONTINUE
           END-EVALUATE
           PERFORM 9000-WRITE-OUTPUT
           READ ACCOUNT-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2100-CALC-COMPOUND.
           COMPUTE WS-RATE-DAILY =
               ACCT-ANNUAL-RATE / 365
      *>   GPT-4 MISSED: No ON SIZE ERROR on interest COMPUTE.
           COMPUTE WS-INTEREST-AMOUNT =
               ACCT-BALANCE *
               ((1 + WS-RATE-DAILY) ** ACCT-DAYS - 1)
           COMPUTE WS-FINAL-BALANCE =
               ACCT-BALANCE + WS-INTEREST-AMOUNT.

       2200-CALC-SIMPLE.
           COMPUTE WS-RATE-DAILY =
               ACCT-ANNUAL-RATE / 365
           COMPUTE WS-INTEREST-AMOUNT =
               ACCT-BALANCE * WS-RATE-DAILY * ACCT-DAYS
           COMPUTE WS-FINAL-BALANCE =
               ACCT-BALANCE + WS-INTEREST-AMOUNT.

       9000-WRITE-OUTPUT.
           MOVE ACCT-NUMBER      TO OUT-ACCT-NUMBER
           MOVE WS-INTEREST-AMOUNT TO OUT-INTEREST
           MOVE WS-FINAL-BALANCE TO OUT-NEW-BALANCE
           MOVE WS-OUTPUT-LINE   TO INTEREST-LINE
           WRITE INTEREST-LINE.

       3000-CLOSE-FILES.
           CLOSE ACCOUNT-FILE
           CLOSE INTEREST-OUTPUT.

       END PROGRAM INTEREST-CALC.
