on run {input, parameters}
    repeat with f in input
        set fAlias to f as alias
        set fName to name of (info for fAlias)
        set fPath to POSIX path of fAlias

        -- Check if file matches the pattern "Mazurek [YEAR] Calendar.doc"
        if fName starts with "Mazurek" and fName ends with "Calendar.doc" then
            -- Wait briefly in case file is still copying
            delay 1

            if fPath ends with ".doc" then
                set outPOSIX to (text 1 thru -5 of fPath) & ".docx"
                set srcFile to POSIX file fPath
                set outFile to POSIX file outPOSIX

                tell application "Microsoft Word"
                    with timeout of 300 seconds
                        set visible to false
                        open srcFile
                        save as active document file name outFile file format 12
                        close active document saving no
                    end timeout
                end tell

                -- Run your Python script with the sync command
                set projectDir to "/Users/matthewmazurek/projects/calendar-sync"
                set docxArg to quoted form of outPOSIX
                set calendarName to "mazurek"
                -- Optional: add --publish flag if you want to auto-publish to git
                -- set publishFlag to " --publish"
                set publishFlag to ""
                set cmd to "cd " & quoted form of projectDir & " && poetry run python ./cli.py sync " & docxArg & " " & calendarName & publishFlag

                tell application "Terminal"
                    activate
                    do script cmd
                end tell
            end if
        end if
    end repeat

    return input
end run