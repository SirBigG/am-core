import React from 'react';

import {orderBy} from '../utils/filters'

import ListPostItem from './ListPostItem'

const PostList = React.createClass({


    getInitialState() {
        return {data: []};
    },
    
    componentDidMount() {
        $.ajax({
            url: this.props.url,
            datatype: 'json',
            cache: false,
            success: function(data) {
                this.setState({data: orderBy(data.results, 2)});
            }.bind(this)
        })
    },
    render() {
        var postNodes = this.state.data.map((group, i) => {
            return (<div className="row" key={i}>
                      <ListPostItem group={group} grid_class={this.props.grid} />
                   </div>)
        });
        return (
            <div id="items">
                {postNodes}
            </div>
        )
    }
});


export default PostList;