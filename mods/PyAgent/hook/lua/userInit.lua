-- PyAgent User Init Hook
-- Enables automatic command-line match launch when /map argument is passed

local mapArg = HasCommandLineArg("/map") and GetCommandLineArg("/map", 1)
if mapArg and mapArg[1] then
    ForkThread(function()
        WaitSeconds(1.0)
        LOG("PyAgent: Auto-launching single-player skirmish match for map: " .. tostring(mapArg[1]))
        local ok, spl = pcall(import, '/lua/SinglePlayerLaunch.lua')
        if ok and spl and spl.StartCommandLineSession then
            spl.StartCommandLineSession(mapArg[1])
        else
            LOG("PyAgent: Could not import SinglePlayerLaunch.lua")
        end
    end)
end
