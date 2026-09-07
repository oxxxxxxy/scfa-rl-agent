-- PyAgent Sim Bootstrap Hook
local PrevBeginSession = BeginSession

function BeginSession()
    ForkThread(function()
        LOG("PyAgent: Starting RL Bridge...")
        local ok, err = pcall(import, '/mods/PyAgent/modules/rl_bridge.lua')
        if not ok then
            LOG("PyAgent Error importing rl_bridge: " .. tostring(err))
            return
        end
        local Bridge = rawget(_G, 'PyAgent_Bridge')
        if type(Bridge) == 'table' and type(Bridge.Start) == 'function' then
            LOG("PyAgent: Initializing Bridge.Start()")
            Bridge.Start()
        else
            LOG("PyAgent: PyAgent_Bridge.Start not found")
        end
    end)
    PrevBeginSession()
end
