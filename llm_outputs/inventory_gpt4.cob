      *> ============================================================
      *> INVENTORY_UPDATE.COB — GPT-4 "Fix" Output
      *> SYNTHETIC EXAMPLE
      *>
      *> GPT-4 BEHAVIOR:
      *>   FIXED:   Added FILE STATUS on TRANSACTION-FILE
      *>   MISSED:  REWRITE still has no FILE STATUS check
      *>   MISSED:  REDEFINES WS-ITEM-QTY still present (COMP-3 bug)
      *>   MISSED:  FILE STATUS on INVENTORY-FILE not used in logic
      *>   NEW BUG: Added COMPUTE for qty without ON SIZE ERROR
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INVENTORY-UPDATE.
       AUTHOR. GPT4-FIX-V1.
       DATE-WRITTEN. 2024-01-15.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INVENTORY-FILE
               ASSIGN TO 'INVMSTR.DAT'
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS INV-ITEM-KEY
               FILE STATUS IS WS-INV-STATUS.
           SELECT TRANSACTION-FILE
               ASSIGN TO 'INVTRANS.DAT'
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-TXN-STATUS.

       DATA DIVISION.
       FILE SECTION.

       FD INVENTORY-FILE.
       01  INVENTORY-RECORD.
           05  INV-ITEM-KEY        PIC X(12).
           05  INV-DESCRIPTION     PIC X(40).
           05  INV-QTY-ON-HAND     PIC 9(7) COMP-3.
           05  INV-REORDER-POINT   PIC 9(5) COMP-3.
           05  INV-UNIT-COST       PIC 9(5)V99 COMP-3.

       FD TRANSACTION-FILE.
       01  TRANSACTION-RECORD.
           05  TXN-ITEM-KEY        PIC X(12).
           05  TXN-TYPE            PIC X(1).
               88  TXN-RECEIPT     VALUE 'R'.
               88  TXN-ISSUE       VALUE 'I'.
               88  TXN-ADJUST      VALUE 'A'.
           05  TXN-QUANTITY        PIC 9(7).

       WORKING-STORAGE SECTION.

       01  WS-STATUS-FLAGS.
           05  WS-INV-STATUS       PIC XX.
               88  INV-SUCCESS     VALUE '00'.
               88  INV-NOT-FOUND   VALUE '23'.
           05  WS-TXN-STATUS       PIC XX.
               88  TXN-OK          VALUE '00'.
           05  WS-EOF-FLAG         PIC X VALUE 'N'.
               88  END-OF-FILE     VALUE 'Y'.
           05  WS-ERROR-COUNT      PIC 9(4) VALUE 0.

       01  WS-WORK-FIELDS.
      *>   GPT-4 MISSED: REDEFINES on COMP-3 field still present.
           05  WS-ITEM-QTY         PIC 9(7) COMP-3.
           05  WS-ITEM-QTY-X       REDEFINES WS-ITEM-QTY PIC X(4).
      *>   GPT-4 NEW BUG: COMPUTE for quantity accumulation added
      *>   without ON SIZE ERROR. Overflow in WS-NEW-QTY is silent.
           05  WS-NEW-QTY          PIC 9(7) COMP-3.

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-OPEN-FILES
           PERFORM 2000-PROCESS-TRANSACTIONS
               UNTIL END-OF-FILE
           PERFORM 3000-CLOSE-FILES
           STOP RUN.

       1000-OPEN-FILES.
           OPEN I-O INVENTORY-FILE
           OPEN INPUT TRANSACTION-FILE
           READ TRANSACTION-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       2000-PROCESS-TRANSACTIONS.
           MOVE TXN-ITEM-KEY TO INV-ITEM-KEY
           READ INVENTORY-FILE
           IF INV-SUCCESS
               EVALUATE TRUE
                   WHEN TXN-RECEIPT
      *>               GPT-4 NEW BUG: COMPUTE without ON SIZE ERROR.
                       COMPUTE WS-NEW-QTY =
                           INV-QTY-ON-HAND + TXN-QUANTITY
                       MOVE WS-NEW-QTY TO INV-QTY-ON-HAND
                   WHEN TXN-ISSUE
                       COMPUTE WS-NEW-QTY =
                           INV-QTY-ON-HAND - TXN-QUANTITY
                       MOVE WS-NEW-QTY TO INV-QTY-ON-HAND
                   WHEN TXN-ADJUST
                       MOVE TXN-QUANTITY TO INV-QTY-ON-HAND
                   WHEN OTHER
                       CONTINUE
               END-EVALUATE
      *>         GPT-4 MISSED: REWRITE still no FILE STATUS check.
               REWRITE INVENTORY-RECORD
           END-IF
           READ TRANSACTION-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.

       3000-CLOSE-FILES.
           CLOSE INVENTORY-FILE
           CLOSE TRANSACTION-FILE.

       END PROGRAM INVENTORY-UPDATE.
