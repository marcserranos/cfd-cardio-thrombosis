HOW TO RUN (about 2 minutes of your time, then the PC works alone for some hours)
==============================================================================

Thank you for helping! Everything is automatic.

BEFORE YOU START
1. Plug the PC into power.
2. Stop the PC from sleeping while it runs:
   Settings > System > Power > "When plugged in, put my device to sleep after" = Never.
   (You can change it back afterwards.)
3. Unzip this folder somewhere simple with no special characters, for example:
       C:\CFD\Case001_Fluent_package
   (Not inside OneDrive and not on a USB stick.)
   You need about 6 GB of free disk space.

RUN
4. Double-click RUN_ME.bat
   - A black window opens and says "Found: ...fluent.exe".
   - Then it says "[1/2] Baseline simulation started". Leave it alone.
   - Fluent works in the background, without its normal window. This is expected.
   - Run 1 takes roughly 3-5 hours. Run 2 (finer mesh) takes roughly 5-8 hours more. If you need the PC back, you can close it once SEND_TO_MARC_A_baseline.zip exists.
   - Do NOT close the black window.

WHEN IT IS DONE (the black window says "ALL DONE")
5. Upload these files to the Google Drive folder Marc sent you:
       SEND_TO_MARC_A_baseline.zip      (the important one, about 2 GB)
       SEND_TO_MARC_B_finemesh.zip      (if it exists)
       fluent_path_used.txt

IF SOMETHING GOES WRONG
- If the black window shows an error or closes very quickly, send Marc:
    a photo of the black window, and the files
    results_A_baseline\transcript_run.txt  and  results_A_baseline\console_log.txt
- If you need the PC back before run 2 finishes, close the black window
  after "[1/2] finished" appears. Run 1 is the important one.
- If Fluent asks for a license or does not start, send Marc a photo of the message.
