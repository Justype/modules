-- Lmod modulefile.lua
-- Author: Ziyue Cheng
-- Almost all of them are automated, you can modify whatis, ModulesHelp, and REF_HOME as needed.
-- Search TOCHANGE to find the targets.
-- You can also load other dependency modules by depends_on().
--     depends_on("java/17.0.12")

local abs_path = myFileName()                   -- absolute path of module, /somewhere/modules/modulefiles/genome-assembly/version.lua
local ref_full_name = myModuleFullName()        -- full name of module, genome-assembly/version
local ref_name = ref_full_name:match("^(.+)/")  -- ref name, genome-assembly
local ref_version = myModuleVersion()           -- ref version, version like star-gencode47-151
local module_root = abs_path:match("^(.+)/.+/.+/")    -- abs path of modules, /somewhere/modules
local ref_root = pathJoin(module_root, "apps", ref_full_name) -- abs path of target app, /somewhere/modules/apps/genome-assembly/version
local current_datetime = os.date("%Y-%m-%d %H:%M:%S") -- Record current datetime

-- TOCHANGE: A brief description using whatis
whatis("Loads " .. ref_name .. " version " .. ref_version)
-- TOCHANGE: Detailed help section
help([[Placeholder for the usage of this module.]])

-- TOCHANGE: Set custom environment variables and aliases
-- setenv("REF_HOME", ref_root)
-- set_alias("apps", "command")

