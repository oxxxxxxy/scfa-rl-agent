-- PyAgent Reinforcement Learning Bridge
-- Communicates with host Python process via Linux Shared Memory (/dev/shm)

local ScenarioUtils = import('/lua/sim/ScenarioUtilities.lua')
local AIUtils = import('/lua/ai/aiutilities.lua')

_G.PyAgent_Bridge = {
    Running = false,
    StepId = 0,
    SHM_DIR = "Z:/dev/shm/",
    OBS_FILE = "Z:/dev/shm/scfa_obs.json",
    OBS_READY = "Z:/dev/shm/scfa_obs.ready",
    ACT_FILE = "Z:/dev/shm/scfa_action.json",
    ACT_READY = "Z:/dev/shm/scfa_action.ready",
    STOP_FILE = "Z:/dev/shm/scfa_stop.flag"
}

-- Faction blueprint tables
local FactionBlueprints = {
    -- 1: UEF
    [1] = {
        MEX = 'ueb1102',
        POWER = 'ueb1101',
        HYDRO = 'ueb1105',
        LAND_FACTORY = 'ueb0101',
        AIR_FACTORY = 'ueb0102',
        PD = 'ueb2101',
        AA = 'ueb2104',
        LAND_SCOUT = 'uel0101',
        LAND_TANK = 'uel0201',
        AIR_INT = 'uea0102'
    },
    -- 2: Aeon
    [2] = {
        MEX = 'uab1102',
        POWER = 'uab1101',
        HYDRO = 'uab1105',
        LAND_FACTORY = 'uab0101',
        AIR_FACTORY = 'uab0102',
        PD = 'uab2101',
        AA = 'uab2104',
        LAND_SCOUT = 'ual0101',
        LAND_TANK = 'ual0201',
        AIR_INT = 'uaa0102'
    },
    -- 3: Cybran
    [3] = {
        MEX = 'urb1102',
        POWER = 'urb1101',
        HYDRO = 'urb1105',
        LAND_FACTORY = 'urb0101',
        AIR_FACTORY = 'urb0102',
        PD = 'urb2101',
        AA = 'urb2104',
        LAND_SCOUT = 'url0101',
        LAND_TANK = 'url0107',
        AIR_INT = 'ura0102'
    },
    -- 4: Seraphim
    [4] = {
        MEX = 'xsb1102',
        POWER = 'xsb1101',
        HYDRO = 'xsb1105',
        LAND_FACTORY = 'xsb0101',
        AIR_FACTORY = 'xsb0102',
        PD = 'xsb2101',
        AA = 'xsb2104',
        LAND_SCOUT = 'xsl0101',
        LAND_TANK = 'xsl0201',
        AIR_INT = 'xsa0102'
    }
}

-- Lightweight pure Lua JSON Serializer
local function SerializeJson(val)
    local t = type(val)
    if t == 'number' then
        return tostring(val)
    elseif t == 'string' then
        return string.format("%q", val)
    elseif t == 'boolean' then
        return val and "true" or "false"
    elseif t == 'table' then
        local isArray = true
        local n = 0
        for k, v in pairs(val) do
            n = n + 1
            if type(k) ~= 'number' or k ~= n then
                isArray = false
                break
            end
        end
        local parts = {}
        if isArray then
            for i, v in ipairs(val) do
                table.insert(parts, SerializeJson(v))
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(val) do
                table.insert(parts, string.format("%q:%s", tostring(k), SerializeJson(v)))
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    else
        return "null"
    end
end

-- Simple key-value parser for action json
local function ParseActionJson(str)
    if not str then return nil end
    local act = {}
    local actionType = string.match(str, '"action"%s*:%s*(%d+)')
    if actionType then act.action = tonumber(actionType) else act.action = 0 end
    
    local stepId = string.match(str, '"step"%s*:%s*(%d+)')
    if stepId then act.step = tonumber(stepId) else act.step = 0 end

    local tx, tz = string.match(str, '"target"%s*:%s*%[%s*([%d%.%-]+)%s*,%s*[%d%.%-]+%s*,%s*([%d%.%-]+)%s*%]')
    if tx and tz then
        act.target = { tonumber(tx), 0, tonumber(tz) }
    end
    return act
end

local function FileExists(path)
    local f = io.open(path, "r")
    if f then
        f:close()
        return true
    end
    return false
end

local function ReadFile(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local content = f:read("*all")
    f:close()
    return content
end

local function WriteFile(path, content)
    local f = io.open(path, "w")
    if not f then return false end
    f:write(content)
    f:flush()
    f:close()
    return true
end

-- Collect State Observation
local function CollectObservation(aiBrain, factionIndex)
    local obs = {
        step = _G.PyAgent_Bridge.StepId,
        game_time = GetGameTimeSeconds(),
        game_tick = GetGameTick(),
        is_over = IsGameOver(),
        economy = {},
        acu = { alive = false },
        counts = {
            engineers = 0,
            factories_land = 0,
            factories_air = 0,
            combat_land = 0,
            combat_air = 0,
            energy_prod = 0,
            mex = 0
        },
        enemy_threat = {}
    }

    -- Economy
    obs.economy.mass_stored = aiBrain:GetEconomyStored('MASS')
    obs.economy.mass_income = aiBrain:GetEconomyIncome('MASS')
    obs.economy.mass_usage = aiBrain:GetEconomyUsage('MASS')
    obs.economy.mass_trend = aiBrain:GetEconomyTrend('MASS')

    obs.economy.energy_stored = aiBrain:GetEconomyStored('ENERGY')
    obs.economy.energy_income = aiBrain:GetEconomyIncome('ENERGY')
    obs.economy.energy_usage = aiBrain:GetEconomyUsage('ENERGY')
    obs.economy.energy_trend = aiBrain:GetEconomyTrend('ENERGY')

    -- ACU
    local commanders = aiBrain:GetListOfUnits(categories.COMMAND, false)
    if commanders and commanders[1] and not commanders[1]:IsDead() then
        local acu = commanders[1]
        local pos = acu:GetPosition()
        obs.acu.alive = true
        obs.acu.health = acu:GetHealth()
        obs.acu.max_health = acu:GetMaxHealth()
        obs.acu.pos = { math.floor(pos[1]), math.floor(pos[2]), math.floor(pos[3]) }
        obs.acu.fraction = acu:GetFractionComplete()
    end

    -- Units Counts
    local engs = aiBrain:GetListOfUnits(categories.ENGINEER, false)
    obs.counts.engineers = engs and table.getn(engs) or 0

    local lfac = aiBrain:GetListOfUnits(categories.LAND * categories.FACTORY, false)
    obs.counts.factories_land = lfac and table.getn(lfac) or 0

    local afac = aiBrain:GetListOfUnits(categories.AIR * categories.FACTORY, false)
    obs.counts.factories_air = afac and table.getn(afac) or 0

    local lcomb = aiBrain:GetListOfUnits(categories.LAND * categories.MOBILE * categories.DIRECTFIRE, false)
    obs.counts.combat_land = lcomb and table.getn(lcomb) or 0

    local acomb = aiBrain:GetListOfUnits(categories.AIR * categories.MOBILE * categories.ANTIAIR, false)
    obs.counts.combat_air = acomb and table.getn(acomb) or 0

    local mexes = aiBrain:GetListOfUnits(categories.MASSEXTRACTION, false)
    obs.counts.mex = mexes and table.getn(mexes) or 0

    local pgens = aiBrain:GetListOfUnits(categories.ENERGYPRODUCTION, false)
    obs.counts.energy_prod = pgens and table.getn(pgens) or 0

    -- Highest enemy threat position
    local threatPos = aiBrain:GetHighestThreatPosition(1, true)
    if threatPos then
        obs.enemy_threat.pos = { math.floor(threatPos[1]), 0, math.floor(threatPos[3]) }
    end

    return obs
end

-- Execute Agent Action
local function ExecuteAction(aiBrain, factionIndex, act)
    if not act or act.action == 0 then return end
    local bps = FactionBlueprints[factionIndex] or FactionBlueprints[3]

    local idleEngs = aiBrain:GetListOfUnits(categories.ENGINEER, true) -- only idle
    local allEngs = aiBrain:GetListOfUnits(categories.ENGINEER, false)
    local eng = (idleEngs and idleEngs[1]) or (allEngs and allEngs[1])

    local commanders = aiBrain:GetListOfUnits(categories.COMMAND, false)
    local acu = commanders and commanders[1] and not commanders[1]:IsDead() and commanders[1]

    local builder = eng or acu
    if not builder then return end

    local bpos = builder:GetPosition()

    -- Action 1: Build Mass Extractor at nearest free spot
    if act.action == 1 and bps.MEX then
        local mexPositions = aiBrain:GetDepositPoints('Mass')
        if mexPositions then
            local bestPos = nil
            local bestDist = 999999
            for _, mp in mexPositions do
                local dist = VDist2(bpos[1], bpos[3], mp[1], mp[3])
                local existing = aiBrain:GetUnitsAroundPoint(categories.MASSEXTRACTION, mp, 4, 'Ally')
                if table.getn(existing) == 0 and dist < bestDist then
                    bestDist = dist
                    bestPos = mp
                end
            end
            if bestPos then
                IssueBuildMobile(builder, {bestPos[1], 0, bestPos[3]}, bps.MEX, {})
            end
        end

    -- Action 2: Build Power Generator
    elseif act.action == 2 and bps.POWER then
        local buildPos = { bpos[1] + 5, 0, bpos[3] + 5 }
        IssueBuildMobile(builder, buildPos, bps.POWER, {})

    -- Action 3: Build Land Factory
    elseif act.action == 3 and bps.LAND_FACTORY then
        local buildPos = { bpos[1] - 8, 0, bpos[3] - 8 }
        IssueBuildMobile(builder, buildPos, bps.LAND_FACTORY, {})

    -- Action 4: Build Air Factory
    elseif act.action == 4 and bps.AIR_FACTORY then
        local buildPos = { bpos[1] + 8, 0, bpos[3] - 8 }
        IssueBuildMobile(builder, buildPos, bps.AIR_FACTORY, {})

    -- Action 5: Build Point Defense
    elseif act.action == 5 and bps.PD then
        local buildPos = { bpos[1] + 12, 0, bpos[3] + 12 }
        IssueBuildMobile(builder, buildPos, bps.PD, {})

    -- Action 6: Queue Land Scout
    elseif act.action == 6 and bps.LAND_SCOUT then
        local factories = aiBrain:GetListOfUnits(categories.LAND * categories.FACTORY, false)
        if factories and factories[1] then
            IssueBuildFactory(factories[1], bps.LAND_SCOUT, 1)
        end

    -- Action 7: Queue Land Tank
    elseif act.action == 7 and bps.LAND_TANK then
        local factories = aiBrain:GetListOfUnits(categories.LAND * categories.FACTORY, false)
        if factories and factories[1] then
            IssueBuildFactory(factories[1], bps.LAND_TANK, 2)
        end

    -- Action 8: Queue Air Interceptor
    elseif act.action == 8 and bps.AIR_INT then
        local factories = aiBrain:GetListOfUnits(categories.AIR * categories.FACTORY, false)
        if factories and factories[1] then
            IssueBuildFactory(factories[1], bps.AIR_INT, 1)
        end

    -- Action 9: Attack Enemy Base / High Threat
    elseif act.action == 9 then
        local combatUnits = aiBrain:GetListOfUnits(categories.MOBILE * categories.LAND * categories.DIRECTFIRE, false)
        if combatUnits and table.getn(combatUnits) > 0 then
            local targetPos = act.target or aiBrain:GetHighestThreatPosition(1, true)
            if targetPos then
                IssueAggressiveMove(combatUnits, targetPos)
            end
        end

    -- Action 10: Defend ACU
    elseif act.action == 10 and acu then
        local combatUnits = aiBrain:GetListOfUnits(categories.MOBILE * categories.LAND * categories.DIRECTFIRE, false)
        if combatUnits and table.getn(combatUnits) > 0 then
            IssueGuard(combatUnits, acu)
        end

    -- Action 11: Reclaim Nearby
    elseif act.action == 11 and builder then
        local pos = builder:GetPosition()
        local reclaimables = GetReclaimablesInRect(pos[1]-25, pos[3]-25, pos[1]+25, pos[3]+25)
        if reclaimables and reclaimables[1] then
            IssueReclaim(builder, reclaimables[1])
        end
    end
end

-- Main RL Loop
function _G.PyAgent_Bridge.Start()
    if _G.PyAgent_Bridge.Running then return end
    _G.PyAgent_Bridge.Running = true

    LOG("PyAgent: Bridge loop entered")
    SetGameSpeed(10) -- Accelerated 10x speed

    local self = _G.PyAgent_Bridge
    -- Find our army (Army 1)
    local aiBrain = GetArmyBrain(1)
    local factionIndex = aiBrain:GetFactionIndex()

    -- Initial delay for landing blast
    WaitTicks(30)

    while not IsGameOver() and not FileExists(self.STOP_FILE) do
        self.StepId = self.StepId + 1

        -- 1. Gather observation
        local obs = CollectObservation(aiBrain, factionIndex)
        local obsJson = SerializeJson(obs)

        -- 2. Write observation to shared memory
        WriteFile(self.OBS_FILE, obsJson)
        WriteFile(self.OBS_READY, tostring(self.StepId))

        -- 3. Wait for Python action (with timeout of ~50 sim ticks = 5 sec)
        local waitCount = 0
        while not FileExists(self.ACT_READY) and waitCount < 50 do
            WaitTicks(1)
            waitCount = waitCount + 1
        end

        -- 4. Process Action if ready
        if FileExists(self.ACT_READY) then
            local actContent = ReadFile(self.ACT_FILE)
            if actContent then
                local act = ParseActionJson(actContent)
                ExecuteAction(aiBrain, factionIndex, act)
            end
            os.remove(self.ACT_READY)
        end

        -- Step interval (10 ticks = 1 game second)
        WaitTicks(10)
    end

    LOG("PyAgent: Match completed or stopped")
    _G.PyAgent_Bridge.Running = false
end
