import { Router, Route, Link, browserHistory, IndexRoute } from 'react-router'

import React from 'react'
import { render } from 'react-dom'

import UserUpdateForm from '../components/forms/UserUpdateForm';
import UserPostForm from '../components/forms/UserPostForm';
import PostList from '../components/PostList'
import NotFound from '../components/NotFound'

// TODO: create dynamic menu with active option
const App = React.createClass({
    render() {
        return(
            <div>
                <div className="col-md-3">
                    <ul className="nav nav-pills nav-stacked">
                        <li role="presentation">
                            <a href={"/user/" + this.props.params.user_id + "/"}>
                                <i className="fa fa-home fo-3x" aria-hidden="true"> Моя сторінка</i>
                            </a>
                        </li>
                        <li role="presentation">
                            <a href={"/user/" + this.props.params.user_id + "/update"}>
                                <i className="fa fa-pencil fo-3x" aria-hidden="true"> Змінити дані</i>
                            </a>
                        </li>
                        <li role="presentation">
                            <a href={"/user/" + this.props.params.user_id + "/post/create"}>
                                <i className="fa fa-newspaper-o fo-3x" aria-hidden="true"> Додати статтю</i>
                            </a>
                        </li>
                    </ul>
                </div>
                <div className="col-md-9">
                    {this.props.children}
                </div>
            </div>
        )
    }
});

const PersonalIndex = React.createClass({
    render(){
        return(
            <div>
                <PostList url="/api/user/posts/" grid="col-sm-6 col-md-6" />
            </div>
        )
    }
});


render((
  <Router history={browserHistory}>
    <Route path="/user/:user_id/" component={App}>
        <IndexRoute component={PersonalIndex} />
        <Route path="update" component={UserUpdateForm}/>
        <Route path="post/create" component={UserPostForm}/>
        <Route path="*" component={NotFound} />
    </Route>
  </Router>
), document.getElementById('root'));