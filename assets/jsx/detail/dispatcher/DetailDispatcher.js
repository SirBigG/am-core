var Dispatcher = require('flux').Dispatcher;


var DetailDispatcher = new Dispatcher();

DetailDispatcher.handleViewAction = (action) => {
  DetailDispatcher.dispatch({
      source: 'VIEW_ACTION',
      action: action
  })
};

DetailDispatcher.handleServerAction = (action) => {
  DetailDispatcher.dispatch({
    source: 'SERVER_ACTION',
    action: action
  });
};

export default DetailDispatcher;
