-- PyAgent Full Programmatic API Bridge for Supreme Commander: Forged Alliance
-- Ultra-low latency IPC via Linux Shared Memory (/dev/shm)

local ScenarioUtils = import('/lua/sim/ScenarioUtilities.lua')
local AIUtils = import('/lua/ai/aiutilities.lua')

_G.PyAgent_Bridge = {
    Running = false,
    StepId = 0,
    ArmyIndex = 1, -- Default to Army 1 (can be switched via command)
    SHM_DIR = "Z:/dev/shm/",
    STATE_FILE = "Z:/dev/shm/scfa_state.json",
    STATE_READY = "Z:/dev/shm/scfa_state.ready",
    CMD_FILE = "Z:/dev/shm/scfa_commands.json",
    CMD_READY = "Z:/dev/shm/scfa_commands.ready",
    STOP_FILE = "Z:/dev/shm/scfa_stop.flag"
}

-- Fast JSON Serializer for Lua
local function SerializeJson(val)
    local t = type(val)
    if t == 'number' then
        if val ~= val then return "0" end -- NaN check
        if val == math.huge then return "999999" end
        if val == -math.huge then return "-999999" end
        return string.format("%.2f", val)
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

-- Category tags helper
local function GetUnitTags(unit)
    local tags = {}
    if EntityCategoryContains(categories.COMMAND, unit) then table.insert(tags, "COMMANDER") end
    if EntityCategoryContains(categories.SUBCOMMANDER, unit) then table.insert(tags, "SUBCOMMANDER") end
    if EntityCategoryContains(categories.ENGINEER, unit) then table.insert(tags, "ENGINEER") end
    if EntityCategoryContains(categories.FACTORY, unit) then table.insert(tags, "FACTORY") end
    if EntityCategoryContains(categories.LAND, unit) then table.insert(tags, "LAND") end
    if EntityCategoryContains(categories.AIR, unit) then table.insert(tags, "AIR") end
    if EntityCategoryContains(categories.NAVAL, unit) then table.insert(tags, "NAVAL") end
    if EntityCategoryContains(categories.STRUCTURE, unit) then table.insert(tags, "STRUCTURE") end
    if EntityCategoryContains(categories.MASSEXTRACTION, unit) then table.insert(tags, "MASSEXTRACTION") end
    if EntityCategoryContains(categories.ENERGYPRODUCTION, unit) then table.insert(tags, "ENERGYPRODUCTION") end
    if EntityCategoryContains(categories.DIRECTFIRE, unit) then table.insert(tags, "DIRECTFIRE") end
    if EntityCategoryContains(categories.INDIRECTFIRE, unit) then table.insert(tags, "INDIRECTFIRE") end
    if EntityCategoryContains(categories.ANTIAIR, unit) then table.insert(tags, "ANTIAIR") end
    if EntityCategoryContains(categories.DEFENSE, unit) then table.insert(tags, "DEFENSE") end
    if EntityCategoryContains(categories.RADAR, unit) then table.insert(tags, "RADAR") end
    if EntityCategoryContains(categories.SONAR, unit) then table.insert(tags, "SONAR") end
    if EntityCategoryContains(categories.OMNI, unit) then table.insert(tags, "OMNI") end
    if EntityCategoryContains(categories.SHIELD, unit) then table.insert(tags, "SHIELD") end
    if EntityCategoryContains(categories.TECH1, unit) then table.insert(tags, "TECH1") end
    if EntityCategoryContains(categories.TECH2, unit) then table.insert(tags, "TECH2") end
    if EntityCategoryContains(categories.TECH3, unit) then table.insert(tags, "TECH3") end
    if EntityCategoryContains(categories.EXPERIMENTAL, unit) then table.insert(tags, "EXPERIMENTAL") end
    return tags
end

-- Collect comprehensive game state
local function CollectFullState(aiBrain)
    local mapWidth = (ScenarioInfo.size and ScenarioInfo.size[1]) or 512
    local mapHeight = (ScenarioInfo.size and ScenarioInfo.size[2]) or 512

    local state = {
        step = _G.PyAgent_Bridge.StepId,
        army_index = _G.PyAgent_Bridge.ArmyIndex,
        game_time = GetGameTimeSeconds(),
        game_tick = GetGameTick(),
        game_speed = GetGameSpeed(),
        is_over = IsGameOver(),
        map = {
            width = mapWidth,
            height = mapHeight
        },
        economy = {
            mass = {
                stored = aiBrain:GetEconomyStored('MASS'),
                capacity = aiBrain:GetEconomyStorage('MASS'),
                income = aiBrain:GetEconomyIncome('MASS'),
                usage = aiBrain:GetEconomyUsage('MASS'),
                requested = aiBrain:GetEconomyRequested('MASS'),
                trend = aiBrain:GetEconomyTrend('MASS')
            },
            energy = {
                stored = aiBrain:GetEconomyStored('ENERGY'),
                capacity = aiBrain:GetEconomyStorage('ENERGY'),
                income = aiBrain:GetEconomyIncome('ENERGY'),
                usage = aiBrain:GetEconomyUsage('ENERGY'),
                requested = aiBrain:GetEconomyRequested('ENERGY'),
                trend = aiBrain:GetEconomyTrend('ENERGY')
            }
        },
        units = {},
        enemies = {},
        mass_spots = {}
    }

    -- Friendly Units with individual resource production/consumption and build rate
    local myUnits = aiBrain:GetListOfUnits(categories.ALLUNITS, false)
    if myUnits then
        for _, u in ipairs(myUnits) do
            if not u:IsDead() then
                local pos = u:GetPosition()
                local bp = u:GetBlueprint()
                table.insert(state.units, {
                    id = u:GetEntityId(),
                    bp = bp.BlueprintId,
                    pos = { math.floor(pos[1]*10)/10, math.floor(pos[2]*10)/10, math.floor(pos[3]*10)/10 },
                    hp = u:GetHealth(),
                    max_hp = u:GetMaxHealth(),
                    fraction = u:GetFractionComplete(),
                    tags = GetUnitTags(u),
                    mass_in = u.GetProductionPerSecondMass and u:GetProductionPerSecondMass() or 0,
                    mass_out = u.GetConsumptionPerSecondMass and u:GetConsumptionPerSecondMass() or 0,
                    energy_in = u.GetProductionPerSecondEnergy and u:GetProductionPerSecondEnergy() or 0,
                    energy_out = u.GetConsumptionPerSecondEnergy and u:GetConsumptionPerSecondEnergy() or 0,
                    build_rate = u.GetBuildRate and u:GetBuildRate() or 0,
                    fuel = u.GetFuelRatio and u:GetFuelRatio() or 1.0
                })
            end
        end
    end

    -- Spotted / Visible Enemy Units (Line of Sight + Radar + Omni)
    local center = { mapWidth / 2, 0, mapHeight / 2 }
    local radius = math.max(mapWidth, mapHeight) * 1.5
    local enemyUnits = aiBrain:GetUnitsAroundPoint(categories.ALLUNITS, center, radius, 'Enemy')
    if enemyUnits then
        for _, u in ipairs(enemyUnits) do
            if not u:IsDead() then
                local pos = u:GetPosition()
                local bp = u:GetBlueprint()
                table.insert(state.enemies, {
                    id = u:GetEntityId(),
                    bp = bp.BlueprintId,
                    pos = { math.floor(pos[1]*10)/10, math.floor(pos[2]*10)/10, math.floor(pos[3]*10)/10 },
                    hp = u:GetHealth(),
                    max_hp = u:GetMaxHealth(),
                    tags = GetUnitTags(u)
                })
            end
        end
    end

    -- Mass Deposits & Occupancy
    local massPoints = aiBrain:GetDepositPoints('Mass')
    if massPoints then
        for _, mp in ipairs(massPoints) do
            local allies = aiBrain:GetUnitsAroundPoint(categories.MASSEXTRACTION, mp, 4, 'Ally')
            local enemies = aiBrain:GetUnitsAroundPoint(categories.MASSEXTRACTION, mp, 4, 'Enemy')
            local occ = "free"
            if allies and table.getn(allies) > 0 then
                occ = "ally"
            elseif enemies and table.getn(enemies) > 0 then
                occ = "enemy"
            end
            table.insert(state.mass_spots, {
                x = math.floor(mp[1]*10)/10,
                z = math.floor(mp[3]*10)/10,
                status = occ
            })
        end
    end

    return state
end

-- Resolve list of unit objects from IDs
local function ResolveUnits(unitIds)
    local list = {}
    if type(unitIds) == "table" then
        for _, id in ipairs(unitIds) do
            local u = GetUnitById(id)
            if u and not u:IsDead() then
                table.insert(list, u)
            end
        end
    elseif type(unitIds) == "number" then
        local u = GetUnitById(unitIds)
        if u and not u:IsDead() then
            table.insert(list, u)
        end
    end
    return list
end

-- Execute a single command
local function ExecuteCommand(cmd)
    if not cmd or not cmd.type then return end
    local ctype = cmd.type

    -- Move
    if ctype == "move" and cmd.units and cmd.target then
        local units = ResolveUnits(cmd.units)
        if table.getn(units) > 0 then
            IssueMove(units, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] })
        end

    -- Attack Move
    elseif ctype == "attack_move" and cmd.units and cmd.target then
        local units = ResolveUnits(cmd.units)
        if table.getn(units) > 0 then
            IssueAggressiveMove(units, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] })
        end

    -- Attack Unit
    elseif ctype == "attack" and cmd.units and cmd.target_id then
        local units = ResolveUnits(cmd.units)
        local target = GetUnitById(cmd.target_id)
        if table.getn(units) > 0 and target and not target:IsDead() then
            IssueAttack(units, target)
        end

    -- Guard / Assist
    elseif ctype == "guard" and cmd.units and cmd.target_id then
        local units = ResolveUnits(cmd.units)
        local target = GetUnitById(cmd.target_id)
        if table.getn(units) > 0 and target and not target:IsDead() then
            IssueGuard(units, target)
        end

    -- Patrol
    elseif ctype == "patrol" and cmd.units and cmd.target then
        local units = ResolveUnits(cmd.units)
        if table.getn(units) > 0 then
            IssuePatrol(units, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] })
        end

    -- Stop
    elseif ctype == "stop" and cmd.units then
        local units = ResolveUnits(cmd.units)
        if table.getn(units) > 0 then
            IssueStop(units)
        end

    -- Build Mobile (Engineer / ACU / SACU)
    elseif ctype == "build_mobile" and cmd.builder and cmd.blueprint and cmd.target then
        local builder = GetUnitById(cmd.builder)
        if builder and not builder:IsDead() then
            IssueBuildMobile(builder, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] }, cmd.blueprint, {})
        end

    -- Build Factory (Produce units / experimentals / planes / ships / tanks)
    elseif ctype == "build_factory" and cmd.factory and cmd.blueprint then
        local factory = GetUnitById(cmd.factory)
        if factory and not factory:IsDead() then
            local count = cmd.count or 1
            IssueBuildFactory(factory, cmd.blueprint, count)
        end

    -- Upgrade Structure (Factory T1->T2->T3, Mex T1->T2->T3, Radar T1->T2->Omni)
    elseif ctype == "upgrade" and cmd.unit and cmd.blueprint then
        local unit = GetUnitById(cmd.unit)
        if unit and not unit:IsDead() then
            IssueUpgrade(unit, cmd.blueprint)
        end

    -- Enhance ACU / SACU (Gunnery, RAS, Shield, Stealth, Engineering suites)
    elseif ctype == "enhance" and cmd.unit and cmd.enhancement then
        local unit = GetUnitById(cmd.unit)
        if unit and not unit:IsDead() then
            IssueScript({unit}, { TaskName = "EnhanceTask", Enhancement = cmd.enhancement })
        end

    -- Reclaim Target or Area
    elseif ctype == "reclaim" and cmd.builder then
        local builder = GetUnitById(cmd.builder)
        if builder and not builder:IsDead() then
            if cmd.target_id then
                local target = GetEntityById(cmd.target_id)
                if target then IssueReclaim(builder, target) end
            elseif cmd.target then
                local pos = cmd.target
                local reclaimables = GetReclaimablesInRect(pos[1]-15, pos[3]-15, pos[1]+15, pos[3]+15)
                if reclaimables and reclaimables[1] then
                    IssueReclaim(builder, reclaimables[1])
                end
            end
        end

    -- Overcharge
    elseif ctype == "overcharge" and cmd.commander and cmd.target then
        local acu = GetUnitById(cmd.commander)
        if acu and not acu:IsDead() then
            IssueOverCharge(acu, { cmd.target[1], cmd.target[2] or 0, cmd.target[3] })
        end

    -- Game Speed
    elseif ctype == "set_speed" and cmd.speed then
        SetGameSpeed(tonumber(cmd.speed))

    -- Switch controlled army
    elseif ctype == "set_army" and cmd.army then
        _G.PyAgent_Bridge.ArmyIndex = tonumber(cmd.army)
    end
end

-- Lightweight Command Batch Parser
local function ExecuteCommandsJson(str)
    if not str then return end
    for obj in string.gfind(str, '(%{[^%}%{]+%})') do
        local cmd = {}
        cmd.type = string.match(obj, '"type"%s*:%s*"([^"]+)"')
        
        local bp = string.match(obj, '"blueprint"%s*:%s*"([^"]+)"')
        if bp then cmd.blueprint = bp end

        local enh = string.match(obj, '"enhancement"%s*:%s*"([^"]+)"')
        if enh then cmd.enhancement = enh end

        local bldr = string.match(obj, '"builder"%s*:%s*(%d+)')
        if bldr then cmd.builder = tonumber(bldr) end

        local fct = string.match(obj, '"factory"%s*:%s*(%d+)')
        if fct then cmd.factory = tonumber(fct) end

        local unt = string.match(obj, '"unit"%s*:%s*(%d+)')
        if unt then cmd.unit = tonumber(unt) end

        local tid = string.match(obj, '"target_id"%s*:%s*(%d+)')
        if tid then cmd.target_id = tonumber(tid) end

        local cnt = string.match(obj, '"count"%s*:%s*(%d+)')
        if cnt then cmd.count = tonumber(cnt) end

        local spd = string.match(obj, '"speed"%s*:%s*(%d+)')
        if spd then cmd.speed = tonumber(spd) end

        local arm = string.match(obj, '"army"%s*:%s*(%d+)')
        if arm then cmd.army = tonumber(arm) end

        local tx, tz = string.match(obj, '"target"%s*:%s*%[%s*([%d%.%-]+)%s*,%s*[%d%.%-]+%s*,%s*([%d%.%-]+)%s*%]')
        if tx and tz then
            cmd.target = { tonumber(tx), 0, tonumber(tz) }
        end

        local unitsPart = string.match(obj, '"units"%s*:%s*%[([^%]]+)%]')
        if unitsPart then
            cmd.units = {}
            for uid in string.gfind(unitsPart, '(%d+)') do
                table.insert(cmd.units, tonumber(uid))
            end
        end

        ExecuteCommand(cmd)
    end
end

-- Main Sim Hook Loop
function _G.PyAgent_Bridge.Start()
    if _G.PyAgent_Bridge.Running then return end
    _G.PyAgent_Bridge.Running = true

    LOG("PyAgent: Full API Bridge starting...")
    SetGameSpeed(10)

    local self = _G.PyAgent_Bridge

    -- Wait 30 ticks for ACU landing animation to finish
    WaitTicks(30)

    while not IsGameOver() and not FileExists(self.STOP_FILE) do
        self.StepId = self.StepId + 1

        local aiBrain = GetArmyBrain(self.ArmyIndex)
        if aiBrain then
            -- 1. Harvest complete state
            local state = CollectFullState(aiBrain)
            local stateJson = SerializeJson(state)

            -- 2. Publish state to /dev/shm
            WriteFile(self.STATE_FILE, stateJson)
            WriteFile(self.STATE_READY, tostring(self.StepId))
        end

        -- 3. Wait for Python commands handshake (up to 5 seconds timeout)
        local waitCount = 0
        while not FileExists(self.CMD_READY) and waitCount < 50 and not FileExists(self.STOP_FILE) do
            WaitTicks(1)
            waitCount = waitCount + 1
        end

        -- 4. Process incoming commands
        if FileExists(self.CMD_READY) then
            local cmdJson = ReadFile(self.CMD_FILE)
            if cmdJson then
                ExecuteCommandsJson(cmdJson)
            end
            os.remove(self.CMD_READY)
        end

        -- Step advance (10 sim ticks = 1 game second)
        WaitTicks(10)
    end

    LOG("PyAgent: Bridge finished session.")
    _G.PyAgent_Bridge.Running = false
end
