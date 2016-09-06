import React from 'react';

import {truncate} from '../utils/filters'


const ListPostItem = React.createClass({
    render() {
        var groupNodes = this.props.group.map((post, i) => {
            return <div className={this.props.grid_class} key={ i }>
                <div className="item_in_list">
                    <img src={post.photo.image} alt={ post.photo.description } id="image-list-size" className="img-rounded img-responsive" />
                    <a href={ post.url }><h1 className="text-center">{ post.title }</h1></a>
                    <div className="text-justify" dangerouslySetInnerHTML={{__html: truncate(post.text, 40) }} />
                </div>
            </div>
            });
        return (
            <div>
                {groupNodes}
            </div>
        )
    }
});


export default ListPostItem;
