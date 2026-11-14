import unreal as u
from editor_toolset.toolsets.blueprint import BlueprintTools as B

ROOT = '/Game/Bumpit/Blueprints/'
HUD = u.load_asset(ROOT + 'BP_BumpitHUD')
RULES = u.load_asset(ROOT + 'BP_RoundRules')
CP = {HUD: ROOT+'BP_BumpitHUD.BP_BumpitHUD_C', RULES: ROOT+'BP_RoundRules.BP_RoundRules_C'}

def put(pin, value):
    pin.break_pin_links()
    if isinstance(value, u.BlueprintGraphPin):
        assert value.try_create_connection(pin), 'Connection failed'
    else:
        assert pin.set_pin_value(str(value).lower() if isinstance(value, bool) else str(value)), str(value)

class Graph:
    def __init__(self, bp, name, clear=False):
        self.bp = bp
        names = {g.get_name(): g for g in B.list_graphs(bp)}
        self.g = names.get(name) or B.add_function_graph(bp, name)
        self.e = u.BlueprintGraphEditor.get_graph_editor(self.g)
        self.nodes = {n.get_name(): n for n in B.find_nodes(self.g)}
        if clear:
            for n in list(self.nodes.values()):
                if n.get_class().get_name() not in ('K2Node_FunctionEntry', 'K2Node_FunctionResult'):
                    B.delete_node(n)
            for n in B.find_nodes(self.g):
                for p in B._get_node_info(n).input_pins + B._get_node_info(n).output_pins:
                    B._resolve_pin(p.pin_id).break_pin_links()
        self.entry = self.e.find_graph_entry_pin()
        self.tail = self.entry
    def old(self, name): return self.nodes[name]
    def arg(self, name): return self.entry.get_owning_node().find_output_pin(name)
    def get(self, name, other=None):
        n = self.e.add_get_member_variable_node(name, CP[other] if other else '')
        if other: put(n.find_input_pin('self'), self.get('Rules' if other == RULES else 'Hud'))
        return n.find_output_pin(name)
    def set(self, name, value, other=None):
        n = self.e.add_set_member_variable_node(name, CP[other] if other else '')
        if other: put(n.find_input_pin('self'), self.get('Rules' if other == RULES else 'Hud'))
        put(n.find_input_pin(name), value)
        self.exec(n)
        return n
    def exec(self, n):
        put(n.find_execute_pin(), self.tail)
        self.tail = n.find_then_pin()
        return n
    def call(this, path, **args):
        n = this.e.add_call_function_node(path)
        assert n, path
        for k,v in args.items(): put(n.find_input_pin(k), v)
        return n
    def action(this, path, **args): return this.exec(this.call(path, **args))
    def math(self, name, a, b=None):
        args = {'A': a}
        if b is not None: args['B'] = b
        if isinstance(b,u.BlueprintGraphPin) and not isinstance(a,u.BlueprintGraphPin): args={'B':b,'A':a}
        return self.call('/Script/Engine.KismetMathLibrary:'+name, **args).find_output_pin('ReturnValue')
    def branch(self, cond):
        n = self.e.add_branch_node()
        put(n.find_input_pin('Condition'), cond)
        put(n.find_execute_pin(), self.tail)
        return n.find_output_pin('then'), n.find_output_pin('else')
    def reject(self, cond, message=None):
        yes,no = self.branch(cond)
        self.tail = yes
        if message: self.set('Message', message, HUD if self.bp == RULES else None)
        r = self.e.add_return_node()
        put(r.find_execute_pin(), self.tail)
        self.tail = no
    def ret(self, value, name='ReturnValue'):
        r = self.e.add_return_node()
        put(r.find_input_pin(name), value)
        put(r.find_execute_pin(), self.tail)
    def textnum(self, prefix, value, suffix='', append=''):
        return self.call('/Script/Engine.KismetStringLibrary:BuildString_Int', AppendTo=append, Prefix=prefix, InInt=value, Suffix=suffix).find_output_pin('ReturnValue')
    def msg(self, text): self.set('Message', text)
    def rulecall(self, name, **args):
        args['self'] = self.get('Rules')
        return self.call(CP[RULES]+':'+name, **args)
    def pin(self, node, pin): return self.old(node).find_input_pin(pin)

def rulesvar(name, kind, default):
    if name not in B.list_variables(RULES): B.add_variable(RULES,name,kind)
    B.compile_blueprint(RULES)
    B.get_default_object(RULES).set_editor_property(name,default)
