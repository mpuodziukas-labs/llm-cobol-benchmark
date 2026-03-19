      *> ============================================================
      *> PAYROLL_CALCULATION.COB
      *> Acme Corp Payroll — Gross Pay with Overtime
      *> PURPOSE: Calculate gross pay; full-time gets 1.5x after 40hrs
      *>
      *> INTENTIONAL BUG PATTERN (common LLM failure):
      *>   BUG #1 — PIC V99 drops integer: WS-OVERTIME-RATE declared
      *>            PIC V99 so COMPUTE result of $15.00 becomes $0.00.
      *>   BUG #2 — No ON SIZE ERROR on COMPUTE WS-GROSS-PAY.
      *>   BUG #3 — WHEN OTHER CONTINUE passes invalid records through.
      *>   BUG #4 — No FILE STATUS on EMPLOYEE-FILE or PAYROLL-REPORT.
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL-CALC.
       AUTHOR. ACME-CORP.
       DATE-WRITTEN. 1989-03-01.

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
      *>   BUG #1: PIC V99 — no integer positions.
      *>   When EMP-RATE=$10.00, 1.5×10=$15.00 stored here = $0.00.
      *>   FLSA overtime violation: employees underpaid on OT hours.
           05  WS-OVERTIME-RATE    PIC V99.
           05  WS-BASE-PAY         PIC 9(7)V99.
           05  WS-OVERTIME-PAY     PIC 9(7)V99.
           05  WS-GROSS-PAY        PIC 9(7)V99.
           05  WS-OVERTIME-HOURS   PIC 9(3)V99.
           05  WS-REGULAR-HOURS    PIC 9(3)V99.
           05  WS-OVERTIME-MULT    PIC 9(1)V99 VALUE 1.50.

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
      *>         BUG #3: invalid EMP-TYPE writes garbage pay record.
               WHEN OTHER
                   CONTINUE
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
      *>         BUG #1 in action: result $15.00 → $0.00 stored.
               COMPUTE WS-OVERTIME-RATE =
                   EMP-RATE * WS-OVERTIME-MULT
      *>         BUG #2: no ON SIZE ERROR. Overflow = silent truncation.
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
