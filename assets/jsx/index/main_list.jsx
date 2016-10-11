import React from 'react';
import ReactDOM from 'react-dom';

import PostList from '../components/PostList'

ReactDOM.render(<PostList url='/api/post/all/' grid="col-sm-12 col-md-6"/>, document.getElementById('main-list'));
