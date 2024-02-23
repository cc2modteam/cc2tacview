g_is_exit = false
g_state_counter = 0
g_vehicle_id = 0


function update(screen_w, screen_h, ticks)

    do_tacview(ticks)

    if update_get_is_focus_local() then
        g_state_counter = g_state_counter + 1
    else
        g_state_counter = 0
    end

    if g_state_counter > 1 then
        if g_is_exit then
            if g_vehicle_id ~= 0 then
                g_vehicle_id = 0
                g_state_counter = 0
            else
                g_is_exit = false
                g_state_counter = 0
                update_set_screen_state_exit()
            end
        elseif update_get_is_focus_local() and update_get_screen_state_active() then
            local vehicle = update_get_screen_vehicle()
    
            if vehicle:get() and g_vehicle_id ~= vehicle:get_id() then
                g_state_counter = 0
                g_vehicle_id = vehicle:get_id() 
            end
        end
    end
    
    update_set_screen_vehicle_control_id(g_vehicle_id)
    
    update_ui_rectangle(7, 6, screen_w / 2 - 9, screen_h - 13, color8(64, 128, 255, 255))
    update_ui_rectangle(screen_w / 2 + 2, 6, screen_w / 2 - 9, screen_h - 13, color8(64, 128, 255, 255))
end

function input_event(event, action)
    if action == e_input_action.release then
        if event == e_input.back then
            g_is_exit = true
            g_state_counter = 0
        end
    end
end


g_last_tacview_tick = 0
g_tacview_thread = tostring( {} ):sub(8) -- extracts the "address" part
g_tacview_debug = 1
g_tacview_errors = {}
g_tacview_skip = false
g_tacview_drydock = nil

function tacview_table_contains(tab, needle)
    for _, v in pairs(tab) do
        if v == needle then
            return true
        end
    end
end

function tacview_log_info(msg)
    print(string.format("log:%s", msg))
end

function tacview_debug_pcall(callable)
    local success, err = pcall(callable)
    if g_tacview_debug == 1 then
        if not success then
            pcall(function()
                local errmsg = string.format("tacview %s error: %s", g_tacview_thread, err)
                if not tacview_table_contains(g_tacview_errors, errmsg) then
                    print(errmsg)
                end
                g_tacview_errors[#g_tacview_errors+1] = errmsg
            end)
        end
    end
    return success, err
end


function format_time(time)
    local seconds = math.floor(time) % 60
    local minutes = math.floor(time / 60) % 60
    local hours = math.min(math.floor(time / 60 / 60), 99)

    return string.format("%02.f:%02.f:%02.f", hours, minutes, seconds)
end

function tacview_out(msg)
    tacview_debug_pcall(function()
        print(string.format("tac:%s", msg))
    end)
end

function get_drydock()
    -- get any drydock
    local vehicle_count = update_get_map_vehicle_count()
    for i = 0, vehicle_count - 1, 1 do
        local vehicle = update_get_map_vehicle_by_index(i)
        if vehicle:get() then
            local def = vehicle:get_definition_index()
            if def == e_game_object_type.drydock then
                g_tacview_drydock = vehicle:get_id()
                return
            end
        end
    end
end

function get_altitude(vid)
    local vect = update_get_map_vehicle_position_relate_to_parent_vehicle(g_tacview_drydock, vid)
    return vect:y()
end

function do_tacview(arg)
    local st, err = pcall(_do_tacview, arg)
    if not st then
        print(err)
    end
end

function _be_tacview()
    -- if we are attached to the last carroer on our team, run, else skip
    local self = update_get_screen_vehicle()
    if self:get() then
        local vteam = update_get_screen_team_id()
        local vdef = self:get_definition_index()
        if vdef ~= e_game_object_type.chassis_carrier then
            g_tacview_skip = true
        else
            -- we are a lifeboat, skip if we are not the last lifeboat
            local vehicle_count = update_get_map_vehicle_count()
            local last_crr = nil

            for i = 0, vehicle_count - 1, 1 do
                local vehicle = update_get_map_vehicle_by_index(i)
                if vehicle:get() then
                    local vdef = vehicle:get_definition_index()
                    if vdef == e_game_object_type.chassis_carrier then
                        if vteam == vehicle:get_team() then
                            -- crr on our team
                            last_crr = vehicle
                        end
                    end
                end
            end

            if last_crr ~= nil then
                if last_crr:get_id() ~= self:get_id() then
                    -- we are not the last crr, dont do tacview
                    g_tacview_skip = true
                end
            end
        end
    end
end


g_vehicles = {}
g_islands = {}

g_tick = 0

function _do_tacview(arg)
    _be_tacview()

    if g_tacview_skip then
        return
    end

    if g_tacview_drydock == nil then
        get_drydock()
    end
    g_tick = update_get_logic_tick()
    local now = g_tick / 30  -- seconds since map started

    if g_last_tacview_tick == 0 then
        print("start tacview adapter .." .. g_tacview_thread )
    end

    if g_last_tacview_tick == 0 then
        -- return if we aren't the carrier
        local screen_vehicle = update_get_screen_vehicle()
        if screen_vehicle:get() then
            if screen_vehicle:get_definition_index() ~= e_game_object_type.chassis_carrier then
                g_tacview_skip = true
                return
            else
                print(string.format("tacview %s adapter on lifeboat screen", g_tacview_thread))
            end
        end
    end

    local since_last = g_tick - g_last_tacview_tick

    if since_last < 15 then
        return
    end

    g_last_tacview_tick = g_tick
    tacview_out(string.format("t=%f", now))

    function try_get_details(v, k, vid)
        local v_def = v:get_definition_index()
        local v_team = v:get_team()

        local parent = v:get_attached_parent_id()
        local docked = parent > 0
        local found = {
            team = v_team,
            def = v_def,
            docked = docked,
            hdg = 0,
            alt = 0,
            x = 0,
            y = 0,
            last_sent = 0,  -- last tick we sent a position
        }

        local fwd = v:get_direction()
        local bearing = ((90 - math.atan(fwd:y(), fwd:x()) / math.pi * 180) + 360) % 360
        found.hdg = bearing

        local v_xz = v:get_position_xz()
        local alt = get_altitude(vid)

        found.alt = alt
        found.x = v_xz:x()
        found.y = v_xz:y()

        local old = g_vehicles[vid]

        -- emit each new unit once
        if old == nil or old.def ~= found.def or old.team ~= found.team then
            -- not printed before
            tacview_out(string.format(
                    "%s%s:def=%d,team=%d,docked=%s,x=%f,y=%f,alt=%f,hdg=%f", k, vid,
                    found.def, found.team, found.docked, found.x, found.y, found.alt, found.hdg))
            found.last_sent = g_tick
        else
            found.last_sent = old.last_sent
            -- already seen and output, update things that have changed only
            if found.docked ~= old.docked then
                tacview_out(string.format("%s%s:docked=%s", k, vid, found.docked))
            end

            -- if position changed by more than 4m, print location or if its been longer than 10 sec since we did
            local displaced = math.abs(old.x - found.x) + math.abs(g_vehicles[vid].y - found.y + math.abs(g_vehicles[vid].alt - found.alt))
            if displaced > 4 or g_tick - old.last_sent > 10 then
                tacview_out(string.format(
                "%s%s:x=%f,y=%f,alt=%f,hdg=%f", k, vid,
                        found.x, found.y, found.alt, found.hdg))
                found.last_sent = g_tick
            end
        end
        return found
    end

    function try_get_visible(v)
        local our_team = update_get_screen_team_id()
        if v:get_team() == our_team then
            -- see all our stuff
            return true
        end

        -- see if within 12km of any of our units
        local v_xz = v:get_position_xz()

        local vehicle_count = update_get_map_vehicle_count()
        for i = 0, vehicle_count - 1, 1 do
            local vehicle = update_get_map_vehicle_by_index(i)
            if vehicle:get() then
                if vehicle:get_team() == our_team then
                    local other_xz = vehicle:get_position_xz()
                    local dist = vec2_dist(other_xz, v_xz)
                    if dist < 12000 then
                        return true
                    end
                end
            end
        end
        return false
    end

    local ret, err = tacview_debug_pcall(function()
        -- fyi. note every non-docked vehicle id, if one goes missing, it was destroyed
        local seen = {}
        local vehicle_count = update_get_map_vehicle_count()
        for i = 0, vehicle_count - 1, 1 do
            local vehicle = update_get_map_vehicle_by_index(i)
            if vehicle:get() then
                local vid = vehicle:get_id()
                local visible = try_get_visible(vehicle)

                if visible then
                    local found = try_get_details(vehicle, "u", vehicle:get_id())
                    if found ~= nil then
                        seen[vid] = found
                    end
                end
            end
        end

        local island_count = update_get_tile_count()
        for i = 0, island_count - 1 do
            local island = update_get_tile_by_index(i)
            if island:get() then
                local island_owner = island:get_team_control()

                -- only print islands once or when they are captured
                if g_islands[i] == nil or g_islands[i]:get_team_control() ~= island_owner then
                    local island_pos = island:get_position_xz()
                    local island_size = 2400
                    if island:get_turret_spawn_count() > 3 then
                        island_size = 3000
                        if island:get_turret_spawn_count() > 8 then
                            island_size = 3400
                        end
                    end
                    tacview_out(string.format("b%d:x=%f,y=%f,team=%d,ew=%d,ns=%d,h=5,name=%s", i + 1,
                            island_pos:x(), island_pos:y(), island_owner,
                            island_size, island_size,
                            island:get_name()
                    ))
                    g_islands[i] = island
                end
            end
        end

        if #seen > 0 then
            for vid, _ in pairs(g_vehicles) do
                if seen[vid] == nil then
                    tacview_out(string.format("u%d:destroyed=1", vid))
                    tacview_log_info(string.format("v=%d destroyed", vid))
                end
            end
        end
        g_vehicles = seen
    end)

    if ret == false then
        print(string.format("err:%s", err))
    end
end
