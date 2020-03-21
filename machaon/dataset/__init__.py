from machaon.dataset.dataset import DataViewFactory
from machaon.dataset.filter import DataFilter

#
#
# type date size name
#
#
def list_operation(app, 
    expression: str, 
    dataset_index: str, 
):
    dataview = select_dataview(app, dataset_index)
    if dataview is None:
        return

    dataview = dataview.command_create_view(expression)
    app.bind_data(dataview)
    app.dataview()

#
#
#
def select_dataview(app, dataset_index:str):
    chm = app.select_process_chamber(dataset_index)
    dataview = chm.get_bound_data()
    if dataview is None:
        app.error("プロセス[{}]にはデータが見つかりません".format(chm.get_index()+1))
        return None
    return dataview

#%4 ? name == 30 | column
#%> list --where name == 30 --sort !column