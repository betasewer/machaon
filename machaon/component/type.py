import os
from typing import TYPE_CHECKING

from machaon.types.shell import Path
from machaon.component.component import ComponentName, Component, ComponentSet
from machaon.component.file import FSTransaction

if TYPE_CHECKING:
    from machaon.process import Spirit
    from machaon.app import AppRoot



class ComponentType:
    """ @type trait alias-name [ServerComponent]
    サーバーコンポーネント
    ValueType: 
        machaon.component.component.Component
    """
    def launch(self, compo: Component, app: 'Spirit'):
        """ @task spirit
        """
        compo.launch(app)
        
    def re_launch(self, compo: Component, app: 'Spirit'):
        """ @task spirit
        """
        compo.relaunch(app)

    def constructor(self, app: 'Spirit', value):
        """ @meta spirit
        Params:
            str: コンポーネント名
        """
        cname = ComponentName.parse(value)
        return app.get_root().server_components().load_component(cname)
    
    def stringify(self, compo: Component):
        """ @meta """
        return "<ServerComponent {}>".format(compo.name.stringify())



class ServerComponentKitType:
    """ @type trait alias-name [ServerKit]
    サーバーコンポーネント
    ValueType: 
        machaon.component.component.ComponentSet
    """
    def deploy(self, cset: ComponentSet, app: 'Spirit'):
        """ @task spirit
        """
        app.post("message", "コンポーネントセット'{}'を配備します".format(cset.name))
        
        fs = FSTransaction()
        for c in cset.getall():
            app.post("message", "[{}]".format(c.name.stringify()))
            with app.indent_post(" - "):
                fs += c.deploy(app)
        fs.apply(app)

        app.post("message", "完了")

    def re_deploy(self, cset: ComponentSet, app: 'Spirit'):
        """ @task spirit
        """
        app.post("message", "コンポーネントセット'{}'を配備し直します".format(cset.name))
        
        fs = FSTransaction()
        for c in cset.getall():
            app.post("message", "[{}]".format(c.name.stringify()))
            with app.indent_post(" - "):
                fs += c.deploy(app, force=True)
        fs.apply(app)

        app.post("message", "完了")

    def component(self, cset: ComponentSet, app: 'Spirit', name: str):
        """ @method spirit
        コンポーネントを取得する 
        Params:
            name(Str):
        Returns:
            ServerComponent:
        """
        return cset.get(name)
    
    def constructor(self, app: 'Spirit', value):
        """ @meta spirit
        Params:
            str: コンポーネントセット名
        """
        return app.get_root().server_components().load(value)
    
    def stringify(self, cset: ComponentSet):
        """ @meta """
        return "<ServerKit {}>".format(cset.name)
