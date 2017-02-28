import React from 'react';
import 'whatwg-fetch';

import {orderBy} from '../utils/filters'

import ListPostItem from './ListPostItem'

const PostList = React.createClass({

    getInitialState() {
        return {data: undefined, previous: "", next: "", url: ""};
    },
    componentWillReceiveProps(newProps) {
        this.setState({url: newProps.url});
    },
    componentDidMount() {
        if (this.state.url){
            this.fetchData(this.state.url)
        } else {
            this.fetchData(this.props.url)
        }
    },
    fetchData(url){
        fetch(url,
            {
                method: 'GET',
                credentials: 'same-origin',
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            }
        )
            .then(
                (response) => {
                    if (response.status === 200){
                        response.json().then((json) => {this.setState({data: orderBy(json.results, 2),
                                                                       previous: json.previous,
                            next: json.next})})
                    }
            }
            );
    },
    onNext(e){
        e.preventDefault();
        this.setState({url: this.state.next});
        this.fetchData(this.state.next);
        // TODO: maybe nicer solusion
        window.scrollTo(0, 0)
    },
    onPrevious(e){
        e.preventDefault();
        this.setState({url: this.state.previous});
        this.fetchData(this.state.previous);
        window.scrollTo(0, 0)
    },
    render() {
        if(!this.state.data){
            return (<div>
                        <i className="fa fa-spinner fa-pulse fa-3x fa-fw"> </i>
                        <p className="sr-only">Loading...</p>
                    </div>
            )
        }
        var postNodes = this.state.data.map((group, i) => {
            return (<div className="row" key={i}>
                      <ListPostItem group={group} grid_class={this.props.grid} />
                   </div>)
        });
        if(this.state.previous){
            var previous = <button aria-label="Previous" type="submit"
                                       className="btn btn-success btn-sm" onClick={this.onPrevious}>
                <span aria-hidden="true">&laquo; Попередня</span></button>
        }
        if(this.state.next){
            var next = <button type="submit" className="btn btn-success btn-sm"
                                   onClick={this.onNext} aria-label="Next">
                <span aria-hidden="true">Наступна &raquo;</span></button>
        }
        return (
            <div>
                <div id="items">
                    {postNodes}
                </div>
                <div className="text-center">
                    {previous}   {next}
                </div>
            </div>
        )
    }
});


export default PostList;