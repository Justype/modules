-- Lmod modulefile.lua
-- Author: Ziyue Cheng
-- Almost all of them are automated, you can modify whatis, ModulesHelp, and APP_HOME as needed.
-- Search TOCHANGE to find the targets.
-- You can also load other modules in this Lmod script.
--     load("java/17.0.12")

local abs_path = myFileName()                   -- absolute path of module, /somewhere/modules/modulefiles/app/x.y.z
local app_full_name = myModuleFullName()        -- full name of module, app/x.y.z
local app_name = app_full_name:match("^(.+)/")  -- app name, app
local app_version = myModuleVersion()           -- app version, x.y.z
local module_root = abs_path:match("^(.+)/.+/.+/")    -- abs path of modules, /somewhere/modules
local app_root = pathJoin(module_root, "apps", app_full_name) -- abs path of target app, /somewhere/modules/apps/app/x.y.z
local current_datetime = os.date("%Y-%m-%d %H:%M:%S") -- Record current datetime

-- TOCHANGE: A brief description using whatis
whatis("Loads " .. app_name .. " version " .. app_version)

-- TOCHANGE: Detailed help section
help([[Placeholder for the usage of this module.]])

-- Display a message when loading the module
if (mode() == "load") then
    io.stderr:write("[" .. current_datetime .. "] Loading module " .. app_full_name .. "\n")
    -- # only display message if not in SLURM
    if os.getenv("SLURM_JOB_ID") == nil then
        io.stderr:write("-----------------------------------------------\n")
        io.stderr:write("  Please use $PICARD to access picard.jar\n")
        io.stderr:write("      or use picard alias (java -jar $PICARD)\n")
        io.stderr:write("-----------------------------------------------\n")
    end
end

-- Display a message when unloading the module
if (mode() == "unload") then
    -- only display message if not in SLURM
    -- if os.getenv("SLURM_JOB_ID") == nil then
    --     io.stderr:write("[" .. current_datetime .. "] Unloading module " .. app_full_name .. "\n")
    -- end
end

-- Set custom environment variables and aliases
setenv("PICARD", pathJoin(app_root, "picard.jar"))
set_alias("picard", "java -jar $PICARD")

-- Handle conflicts with other versions
conflict(app_name)
