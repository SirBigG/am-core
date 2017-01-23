import ReactDOM from 'react-dom';
import CommentsApp from './components/CommentsApp'
import ReviewsApp from './components/ReviewsApp'
import RandomList from './components/RandomList'
import React from 'react';

ReactDOM.render(<RandomList />, document.getElementById('random-post-list'));
ReactDOM.render(<ReviewsApp />, document.getElementById('reviews'));
ReactDOM.render(<CommentsApp />, document.getElementById('comment'));