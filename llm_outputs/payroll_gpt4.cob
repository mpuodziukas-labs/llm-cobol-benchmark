      *> ============================================================
      *> PAYROLL_CALCULATION.COB — GPT-4 "Fix" Output
      *> SYNTHETIC EXAMPLE: Demonstrates common GPT-4 failure modes
      *>
      *> GPT-4 BEHAVIOR:
      *>   FIXED:   PIC V99 → PIC 9V99 (visible, easy pattern)
      *>   MISSED:  ON SIZE ERROR still absent on all COMPUTEs
      *>   MISSED:  WHEN OTHER still CONTINUE (left comment only)
      *>   MISSED:  FILE STATUS still absent on both FDs
      *>   NEW BUG: WS-OVERTIME-MULT precision reduced PIC 9V9→PIC 9V99
      *>            (looks like an "improvement" but changes rounding)
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL-CALC.
       AUTHOR. GPT4-FIX-V1.
       DATE-WRITTEN. 2024-01-15.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMPLOYEE-FILE
               ASSIGN TO 'EMPDATA.DAT'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT PAYROLL-REPORT
               ASSIGN TO 'PAYROLL.RPT'
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.

       FD EMPLOYEE-FILE.
       01  EMPLOYEE-RECORD.
           05  EMP-ID              PIC 9(6).
           05  EMP-NAME            PIC X(30).
           05  EMP-TYPE            PIC X(1).
               88  FULL-TIME       VALUE 'F'.
               88  PART-TIME       VALUE 'P'.
               88  CONTRACTOR      VALUE 'C'.
           05  EMP-HOURS           PIC 9(3)V99.
           05  EMP-RATE            PIC 9(5)V99.

       FD PAYROLL-REPORT.
       01  REPORT-LINE             PIC X(132).

       WORKING-STORAGE SECTION.

       01  WS-FLAGS.
           05  WS-EOF-FLAG         PIC X(1) VALUE 'N'.
               88  END-OF-FILE     VALUE 'Y'.
           05  WS-RECORD-COUNT     PIC 9(6) VALUE 0.

       01  WS-PAYROLL-CALC.
      *>   GPT-4 FIX #1 (CORRECT): PIC V99 → PIC 9V99.
      *>   Integer position added. Basic pattern recognized.
           05  WS-OVERTIME-RATE    PIC 9V99.
           05  WS-BASE-PAY         PIC 9(7)V99.
           05  WS-OVERTIME-PAY     PIC 9(7)V99.
           05  WS-GROSS-PAY        PIC 9(7)V99.
           05  WS-OVERTIME-HOURS   PIC 9(3)V99.
           05  WS-REGULAR-HOURS    PIC 9(3)V99.
      *>   GPT-4 NEW BUG: Changed from PIC 9(1)V99 to PIC 9V9.
      *>   Only 1 decimal place instead of 2. 1.50 → 1.5 looks OK,
      *>   but COMPUTE precision chain now rounds at 1 decimal,
      *>   producing $0.10 errors per hour at high hourly rates.
           05  WS-OVERTIME-MULT    PIC 9V9 VALUE 1.5.

       01  WS-REPORT-LINE.
           05  RPT-EMP-ID          PIC 9(6).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  RPT-EMP-NAME        PIC X(30).
           05  FILLER              PIC X(2) VALUE SPACES.
           05  RPT-GROSS-PAY       PIC $$$,$$$,$$9.99.

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-INITIALIZE
           PERFORM 2000-PROCESS-EMPLOYEES
               UNTIL END-OF-FILE
           PERFORM 3000-FINALIZE
           STOP RUN.

       1000-INITIALIZE.
           OPEN INPUT EMPLOYEE-FILE
           OPEN OUTPUT PAYROLL-REPORT
           READ EMPLOYEE-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2000-PROCESS-EMPLOYEES.
           EVALUATE TRUE
               WHEN FULL-TIME
                   PERFORM 2100-CALC-FULLTIME
               WHEN PART-TIME
                   PERFORM 2200-CALC-PARTTIME
               WHEN CONTRACTOR
                   PERFORM 2300-CALC-CONTRACTOR
      *>         GPT-4 MISSED: WHEN OTHER still CONTINUE.
      *>         GPT-4 added comment "TODO: log invalid type"
      *>         but left CONTINUE. Ghost pay still occurs.
               WHEN OTHER
                   CONTINUE *> TODO: log invalid employee type
           END-EVALUATE
           PERFORM 9000-WRITE-LINE
           ADD 1 TO WS-RECORD-COUNT
           READ EMPLOYEE-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2100-CALC-FULLTIME.
           IF EMP-HOURS > 40
               MOVE 40.00 TO WS-REGULAR-HOURS
               SUBTRACT 40.00 FROM EMP-HOURS
                   GIVING WS-OVERTIME-HOURS
               COMPUTE WS-OVERTIME-RATE =
                   EMP-RATE * WS-OVERTIME-MULT
      *>         GPT-4 MISSED: No ON SIZE ERROR added.
               COMPUTE WS-BASE-PAY =
                   WS-REGULAR-HOURS * EMP-RATE
               COMPUTE WS-OVERTIME-PAY =
                   WS-OVERTIME-HOURS * WS-OVERTIME-RATE
               COMPUTE WS-GROSS-PAY =
                   WS-BASE-PAY + WS-OVERTIME-PAY
           ELSE
               COMPUTE WS-GROSS-PAY = EMP-HOURS * EMP-RATE
           END-IF.

       2200-CALC-PARTTIME.
           COMPUTE WS-GROSS-PAY = EMP-HOURS * EMP-RATE.

       2300-CALC-CONTRACTOR.
           COMPUTE WS-GROSS-PAY = EMP-HOURS * EMP-RATE.

       9000-WRITE-LINE.
           MOVE EMP-ID         TO RPT-EMP-ID
           MOVE EMP-NAME       TO RPT-EMP-NAME
           MOVE WS-GROSS-PAY   TO RPT-GROSS-PAY
           MOVE WS-REPORT-LINE TO REPORT-LINE
           WRITE REPORT-LINE.

       3000-FINALIZE.
           CLOSE EMPLOYEE-FILE
           CLOSE PAYROLL-REPORT.

       END PROGRAM PAYROLL-CALC.
