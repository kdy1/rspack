/** @type {import('../../dist').TStatsAPICaseConfig} */
module.exports = {
	description: "should output the chunks",
	options(context) {
		return {
			context: context.getSource(),
			entry: "./fixtures/chunk-b"
		};
	},
	async check(stats) {
		expect(
			stats?.toJson({
				chunks: true,
				timings: false,
				builtAt: false,
				version: false,
				modulesSpace: 3
			}).chunks
		).toMatchInlineSnapshot(`
		Array [
		  Object {
		    auxiliaryFiles: Array [],
		    children: Array [],
		    childrenByOrder: Object {},
		    entry: false,
		    files: Array [
		      chunkB.js,
		    ],
		    filteredModules: undefined,
		    hash: 64feb0c0aec6d474,
		    id: 250,
		    idHints: Array [],
		    initial: false,
		    modules: Array [
		      Object {
		        assets: Array [],
		        buildTimeExecuted: false,
		        built: true,
		        cacheable: true,
		        cached: false,
		        chunks: Array [
		          250,
		        ],
		        codeGenerated: true,
		        dependent: false,
		        depth: 1,
		        errors: 0,
		        failed: false,
		        filteredReasons: undefined,
		        id: 101,
		        identifier: <TEST_TOOLS_ROOT>/tests/fixtures/b.js,
		        index: 1,
		        index2: 1,
		        issuer: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		        issuerId: 725,
		        issuerName: ./fixtures/chunk-b.js,
		        issuerPath: Array [
		          Object {
		            id: 725,
		            identifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		            name: ./fixtures/chunk-b.js,
		          },
		        ],
		        layer: undefined,
		        moduleType: javascript/auto,
		        name: ./fixtures/b.js,
		        nameForCondition: <TEST_TOOLS_ROOT>/tests/fixtures/b.js,
		        optimizationBailout: Array [
		          Statement with side_effects in source code at ./fixtures/b.js<LINE_COL_RANGE>,
		          ModuleConcatenation bailout: Module is not an ECMAScript module,
		        ],
		        optional: false,
		        orphan: false,
		        postOrderIndex: 1,
		        preOrderIndex: 1,
		        providedExports: null,
		        reasons: Array [
		          Object {
		            active: true,
		            explanation: undefined,
		            loc: undefined,
		            moduleId: 101,
		            moduleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/b.js,
		            moduleName: ./fixtures/b.js,
		            resolvedModule: ./fixtures/b.js,
		            resolvedModuleId: 101,
		            resolvedModuleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/b.js,
		            type: cjs self exports reference,
		            userRequest: self,
		          },
		          Object {
		            active: true,
		            explanation: undefined,
		            loc: undefined,
		            moduleId: 725,
		            moduleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		            moduleName: ./fixtures/chunk-b.js,
		            resolvedModule: ./fixtures/chunk-b.js,
		            resolvedModuleId: 725,
		            resolvedModuleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		            type: import(),
		            userRequest: ./b,
		          },
		        ],
		        size: 94,
		        sizes: Object {
		          javascript: 94,
		        },
		        type: module,
		        usedExports: null,
		        warnings: 0,
		      },
		    ],
		    names: Array [
		      chunkB,
		    ],
		    origins: Array [
		      Object {
		        loc: 2:9-55,
		        module: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		        moduleId: 725,
		        moduleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		        moduleName: ./fixtures/chunk-b.js,
		        request: ./b,
		      },
		    ],
		    parents: Array [
		      909,
		    ],
		    reason: undefined,
		    rendered: true,
		    runtime: Array [
		      main,
		    ],
		    siblings: Array [],
		    size: 94,
		    sizes: Object {
		      javascript: 94,
		    },
		    type: chunk,
		  },
		  Object {
		    auxiliaryFiles: Array [],
		    children: Array [
		      250,
		    ],
		    childrenByOrder: Object {},
		    entry: true,
		    files: Array [
		      main.js,
		    ],
		    filteredModules: undefined,
		    hash: f284da740ad9a1cb,
		    id: 909,
		    idHints: Array [],
		    initial: true,
		    modules: Array [
		      Object {
		        assets: Array [],
		        buildTimeExecuted: false,
		        built: true,
		        cacheable: true,
		        cached: false,
		        chunks: Array [
		          909,
		        ],
		        codeGenerated: true,
		        dependent: false,
		        depth: 0,
		        errors: 0,
		        failed: false,
		        filteredReasons: undefined,
		        id: 725,
		        identifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		        index: 0,
		        index2: 0,
		        issuer: undefined,
		        issuerId: undefined,
		        issuerName: undefined,
		        issuerPath: undefined,
		        layer: undefined,
		        moduleType: javascript/auto,
		        name: ./fixtures/chunk-b.js,
		        nameForCondition: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		        optimizationBailout: Array [
		          Statement with side_effects in source code at ./fixtures/chunk-b.js<LINE_COL_RANGE>,
		          ModuleConcatenation bailout: Module is not an ECMAScript module,
		        ],
		        optional: false,
		        orphan: false,
		        postOrderIndex: 0,
		        preOrderIndex: 0,
		        providedExports: null,
		        reasons: Array [
		          Object {
		            active: true,
		            explanation: undefined,
		            loc: undefined,
		            moduleId: null,
		            resolvedModuleId: null,
		            type: entry,
		            userRequest: ./fixtures/chunk-b,
		          },
		          Object {
		            active: true,
		            explanation: undefined,
		            loc: undefined,
		            moduleId: 725,
		            moduleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		            moduleName: ./fixtures/chunk-b.js,
		            resolvedModule: ./fixtures/chunk-b.js,
		            resolvedModuleId: 725,
		            resolvedModuleIdentifier: <TEST_TOOLS_ROOT>/tests/fixtures/chunk-b.js,
		            type: cjs self exports reference,
		            userRequest: self,
		          },
		        ],
		        size: 85,
		        sizes: Object {
		          javascript: 85,
		        },
		        type: module,
		        usedExports: null,
		        warnings: 0,
		      },
		    ],
		    names: Array [
		      main,
		    ],
		    origins: Array [
		      Object {
		        loc: main,
		        module: ,
		        moduleId: undefined,
		        moduleIdentifier: ,
		        moduleName: ,
		        request: ./fixtures/chunk-b,
		      },
		    ],
		    parents: Array [],
		    reason: undefined,
		    rendered: true,
		    runtime: Array [
		      main,
		    ],
		    siblings: Array [],
		    size: 85,
		    sizes: Object {
		      javascript: 85,
		      runtime: 9140,
		    },
		    type: chunk,
		  },
		]
	`);
	}
};
